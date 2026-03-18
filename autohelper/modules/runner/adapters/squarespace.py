# squarespace.py
"""
Squarespace site adapter.

Hardened scope:
- detect
- extract_pages
- extract_images

Bio/contact/location/CV PDFs are handled upstream via SiteAdapter.extract_metadata(). [file:10]
"""

import asyncio
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from .base import SiteAdapter, SiteMatch

if TYPE_CHECKING:
    from bs4 import BeautifulSoup
    from bs4.element import Tag


def _get_str_attr(tag: "Tag", attr: str, default: str = "") -> str:
    """Safely get string attribute from BS4 tag (handles list returns)."""
    val = tag.get(attr)
    if val is None:
        return default
    if isinstance(val, list):
        return val[0] if val else default
    return val


SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".bmp",
    ".tiff",
    ".avif",
}

# Target Squarespace format. Keep conservative to reduce 404 risk.
TARGET_SQS_FORMAT = "2500w"

BG_URL_RE = re.compile(r"background-image\s*:\s*url\((['\"]?)(.*?)\1\)", re.I)

# Pull any likely Squarespace CDN/static URLs out of embedded JSON/JS
SQS_ANY_URL_RE = re.compile(
    r"(https?://[^\s\"'<>]+(?:squarespace-cdn\.com|static1\.squarespace\.com|images\.squarespace-cdn\.com)[^\s\"'<>]+)",
    re.I,
)

# Extract assetUrl fields from Squarespace JSON blobs (escaped)
SQS_ASSETURL_RE = re.compile(r'"assetUrl"\s*:\s*"([^"]+)"', re.I)


class SquarespaceAdapter(SiteAdapter):
    @property
    def name(self) -> str:
        return "squarespace"

    @property
    def patterns(self) -> list[str]:
        return ["squarespace.com", "squarespace-cdn.com", "static1.squarespace.com", "sqs-"]

    def detect(self, url: str, html: str) -> SiteMatch | None:
        u = (url or "").lower()
        h = (html or "").lower()

        if "squarespace.com" in u or "squarespace-cdn.com" in u:
            return SiteMatch("squarespace", 0.95, {"platform": "squarespace", "detected_by": "url"})

        markers = (
            "static1.squarespace.com",
            "squarespace-cdn.com",
            "sqs-",
            "data-block-type",
            "data-section-id",
        )
        if any(m in h for m in markers):
            return SiteMatch("squarespace", 0.88, {"platform": "squarespace", "detected_by": "html"})

        return None

    async def extract_pages(self, soup: "BeautifulSoup", base_url: str) -> list[str]:
        """
        General page discovery:
        - collect same-domain <a href>
        - lightly score URLs so likely content appears first (since WebCollector crawls only first 10). [file:9]
        """
        base_parsed = urlparse(base_url)
        base_netloc = base_parsed.netloc.lower()

        def _normalize_host(host: str) -> str:
            host = host.lower()
            if host.startswith("www."):
                return host[4:]
            return host

        base_host = _normalize_host(base_netloc)
        urls: list[str] = []

        for a in soup.find_all("a", href=True):
            href = _get_str_attr(a, "href").strip()
            if not href:
                continue
            if href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
                continue

            full = urljoin(base_url, href)
            try:
                pu = urlparse(full)
            except Exception:
                continue

            if _normalize_host(pu.netloc) != base_host:
                continue

            # normalize: drop fragments
            full = urlunparse(pu._replace(fragment=""))
            urls.append(full)

        urls = list(dict.fromkeys(urls))

        def score(u: str) -> int:
            lu = u.lower()

            # de-prioritize obvious non-content / commerce flows
            if any(x in lu for x in ("/cart", "/checkout", "/account", "/login", "/privacy", "/terms")):
                return -50
            if any(x in lu for x in ("/?password=", "/password", "?password=")):
                return -50

            # prefer deeper paths (often actual pages vs home)
            path = urlparse(lu).path.strip("/")
            depth = 0 if not path else path.count("/") + 1

            # mild boosts for common content cues (keep generic)
            boost = 0
            if any(x in lu for x in ("/work", "/portfolio", "/project", "/gallery", "/shop", "/product")):
                boost += 10
            if depth >= 2:
                boost += 3
            if depth >= 3:
                boost += 3

            return boost

        urls.sort(key=score, reverse=True)
        return urls


    async def extract_images(self, soup: "BeautifulSoup", base_url: str) -> list[str]:
        return await asyncio.to_thread(self._extract_images_sync, soup, base_url)

    def _extract_images_sync(self, soup: "BeautifulSoup", base_url: str) -> list[str]:
        out: list[str] = []

        # 0) social/meta images (often highest-quality hero)
        for meta in soup.find_all("meta"):
            prop = (_get_str_attr(meta, "property") or _get_str_attr(meta, "name")).lower()
            if prop in ("og:image", "twitter:image"):
                content = _get_str_attr(meta, "content")
                if content:
                    u = self._normalize_sqs_image(urljoin(base_url, content))
                    if self._is_supported_image(u):
                        out.append(u)

        # 1) <img> and <source> tags (lazy attrs + srcset)
        for el in soup.find_all(["img", "source"]):
            candidates: list[str] = []

            for key in ("src", "data-src", "data-lazy", "data-image", "data-image-url", "data-srcset"):
                v = _get_str_attr(el, key)
                if not v:
                    continue
                if v.startswith("data:"):
                    continue
                candidates.append(v)

            srcset = _get_str_attr(el, "srcset") or _get_str_attr(el, "data-srcset")
            if srcset:
                best = self._best_from_srcset(srcset, base_url)
                if best:
                    candidates.append(best)

            for c in candidates:
                u = self._normalize_sqs_image(urljoin(base_url, c))
                if self._is_supported_image(u):
                    out.append(u)

        # 2) data-image JSON blobs (Squarespace uses these a lot)
        for el in soup.find_all(attrs={"data-image": True}):
            raw = el.get("data-image")
            if not raw or not isinstance(raw, str):
                continue
            raw = raw.strip()

            # can be JSON or a URL; handle both
            if raw.startswith("{") and raw.endswith("}"):
                try:
                    data = json.loads(raw)
                    asset = data.get("assetUrl") or data.get("url")
                    if asset and isinstance(asset, str):
                        u = self._normalize_sqs_image(urljoin(base_url, asset))
                        if self._is_supported_image(u):
                            out.append(u)
                except Exception:
                    pass
            else:
                u = self._normalize_sqs_image(urljoin(base_url, raw))
                if self._is_supported_image(u):
                    out.append(u)

        # 3) inline background images
        for el in soup.find_all(style=True):
            style = _get_str_attr(el, "style")
            for _, raw in BG_URL_RE.findall(style):
                if not raw or raw.startswith("data:"):
                    continue
                u = self._normalize_sqs_image(urljoin(base_url, raw))
                if self._is_supported_image(u):
                    out.append(u)

        # 4) scan embedded scripts/JSON for Squarespace CDN/static URLs
        html_text = str(soup)

        for m in SQS_ANY_URL_RE.finditer(html_text):
            u = m.group(1).replace("\\/", "/")
            u = self._normalize_sqs_image(u)
            if self._is_supported_image(u):
                out.append(u)

        for m in SQS_ASSETURL_RE.finditer(html_text):
            raw = m.group(1).replace("\\/", "/")
            u = self._normalize_sqs_image(urljoin(base_url, raw))
            if self._is_supported_image(u):
                out.append(u)

        return list(dict.fromkeys(out))

    def _best_from_srcset(self, srcset: str, base_url: str) -> str | None:
        # "url 300w, url 1200w, ..."
        best_url: str | None = None
        best_w = -1

        for part in srcset.split(","):
            chunk = part.strip()
            if not chunk:
                continue

            pieces = chunk.split()
            raw_url = pieces[0]
            w = -1

            if len(pieces) > 1 and pieces[1].endswith("w"):
                try:
                    w = int(pieces[1][:-1])
                except Exception:
                    w = -1
            else:
                # no width token; treat later entries as “bigger”
                w = best_w + 1

            resolved = urljoin(base_url, raw_url)
            if w > best_w:
                best_w = w
                best_url = resolved

        return best_url

    def _normalize_sqs_image(self, url: str) -> str:
        """
        If Squarespace provides ?format=###w, bump it to TARGET_SQS_FORMAT for higher resolution.
        Leaves non-Squarespace URLs unchanged.
        """
        try:
            p = urlparse(url)
            q = parse_qs(p.query)

            if "format" in q and q["format"]:
                q["format"] = [TARGET_SQS_FORMAT]
                new_query = urlencode(q, doseq=True)
                return urlunparse(p._replace(query=new_query))

            return url
        except Exception:
            return url

    def _is_supported_image(self, url: str) -> bool:
        try:
            ext = Path(urlparse(url).path).suffix.lower()
            return ext in SUPPORTED_EXTENSIONS
        except Exception:
            return False
