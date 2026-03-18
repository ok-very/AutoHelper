# wordpress.py
"""
WordPress site adapter.

Focus: hardened scope (detect + pages + images).
Bio/contact/location/CV PDFs are handled upstream via SiteAdapter.extract_metadata(). [file:10]
"""

import asyncio
import re
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlparse, urlunparse

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

BG_URL_RE = re.compile(r"background-image\s*:\s*url\((['\"]?)(.*?)\1\)", re.I)
WP_SIZED_RE = re.compile(r"-(\d+)x(\d+)(?=\.[a-zA-Z]{3,5}$)", re.I)

# Pull uploads even when they appear in inline JSON or JS strings
UPLOADS_RE = re.compile(
    r"(https?://[^\s\"'<>)]+/wp-content/uploads/[^\s\"'<>)]+?\.(?:jpg|jpeg|png|gif|webp|bmp|tiff|avif))",
    re.I,
)

# Prioritize likely “work” pages when returning the first N subpages
PROJECT_HINTS = (
    "/work",
    "/project",
    "/projects",
    "/portfolio",
    "/case-study",
    "/case-studies",
)

EXCLUDE_HINTS = (
    "/wp-content/",
    "/wp-includes/",
    "/wp-json/",
    "/feed",
    "/tag/",
    "/category/",
    "/author/",
    "/page/",
    "/search/",
    "?share=",
)


class WordPressAdapter(SiteAdapter):
    @property
    def name(self) -> str:
        return "wordpress"

    @property
    def patterns(self) -> list[str]:
        # Most WP sites are custom domains; these are primarily HTML markers.
        return ["wp-content", "wp-includes", "wp-json", "wp-emoji-release", "wp-block-"]

    def detect(self, url: str, html: str) -> SiteMatch | None:
        h = (html or "").lower()

        # Strong markers
        markers = (
            "wp-content/",
            "wp-includes/",
            "wp-emoji-release",
            "wlwmanifest.xml",  # classic WP marker
            "xmlrpc.php",       # classic WP marker
            "wp-block-",        # block editor classes
        )
        if any(m in h for m in markers):
            return SiteMatch("wordpress", 0.88, {"platform": "wordpress", "detected_by": "html"})

        return None

    async def extract_pages(self, soup: "BeautifulSoup", base_url: str) -> list[str]:
        """
        Return prioritized internal URLs that look like project/work pages.
        WebCollector will only crawl the first slice anyway, so ordering matters.
        """
        base_netloc = urlparse(base_url).netloc.lower()

        prioritized: list[str] = []
        others: list[str] = []

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

            if pu.netloc.lower() != base_netloc:
                continue

            # normalize: remove fragment, keep query (some WP builders use it)
            full = urlunparse(pu._replace(fragment=""))

            low = full.lower()
            if any(x in low for x in EXCLUDE_HINTS):
                continue

            if any(h in low for h in PROJECT_HINTS):
                prioritized.append(full)
            else:
                others.append(full)

        # Deduplicate while preserving order; keep prioritized first
        return list(dict.fromkeys(prioritized + others))

    async def extract_images(self, soup: "BeautifulSoup", base_url: str) -> list[str]:
        return await asyncio.to_thread(self._extract_images_sync, soup, base_url)

    def _extract_images_sync(self, soup: "BeautifulSoup", base_url: str) -> list[str]:
        out: list[str] = []
        base_netloc = urlparse(base_url).netloc.lower()

        # 1) <img> and <source> tags (lazy attrs + srcset)
        for img in soup.find_all(["img", "source"]):
            # Common lazy patterns across WP themes/plugins
            candidates: list[str] = [
                _get_str_attr(img, "src"),
                _get_str_attr(img, "data-src"),
                _get_str_attr(img, "data-lazy-src"),
                _get_str_attr(img, "data-original"),
                _get_str_attr(img, "data-srcset"),  # sometimes present instead of srcset
            ]

            srcset = _get_str_attr(img, "srcset") or _get_str_attr(img, "data-srcset")
            if srcset:
                best = self._best_from_srcset(srcset, base_url)
                if best:
                    candidates.append(best)

            for c in candidates:
                if not c:
                    continue
                if c.startswith("data:"):
                    continue

                u = urljoin(base_url, c)
                if not u:
                    continue

                # Keep: same-domain or wp uploads/media/CDN links (we don’t hard-reject CDNs)
                # If you want to restrict, do it upstream in SSRF checks.
                self._push_wp_image_variants(out, u)

        # 2) linked full-size images (<a href="...jpg">)
        for a in soup.find_all("a", href=True):
            href = _get_str_attr(a, "href").strip()
            if not href:
                continue
            u = urljoin(base_url, href)
            self._push_wp_image_variants(out, u)

        # 3) background-image URLs in inline styles
        for el in soup.find_all(style=True):
            style = _get_str_attr(el, "style")
            for _, raw in BG_URL_RE.findall(style):
                if not raw or raw.startswith("data:"):
                    continue
                u = urljoin(base_url, raw)
                self._push_wp_image_variants(out, u)

        # 4) last resort: regex scan for wp-content/uploads URLs embedded in scripts
        html_text = str(soup)
        for match in UPLOADS_RE.finditer(html_text):
            u = match.group(1)
            self._push_wp_image_variants(out, u)

        # Optional: small heuristic to prefer same-domain uploads first
        # (keeps discovery order mostly intact, but avoids CDNs dominating).
        # You can remove this if you need strict discovery ordering.
        def sort_key(u: str) -> int:
            try:
                netloc = urlparse(u).netloc.lower()
                if netloc == base_netloc:
                    return 0
            except Exception:
                pass
            return 1

        out = list(dict.fromkeys(out))
        out.sort(key=sort_key)
        return out

    def _best_from_srcset(self, srcset: str, base_url: str) -> str | None:
        # "url 300w, url 1024w, ..."
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

            resolved = urljoin(base_url, raw_url)
            if w > best_w:
                best_w = w
                best_url = resolved

        return best_url

    def _push_wp_image_variants(self, out: list[str], url: str) -> None:
        """
        Adds inferred “original” before size-variant when we detect -1024x768.jpg etc.
        We keep both because existence checks are out of scope in adapters.
        """
        if not self._is_supported_image(url):
            return

        # Ignore common non-art assets when they appear as tiny placeholders
        low = url.lower()
        if any(x in low for x in ("/emoji/", "gravatar.com/avatar", "data:image")):
            return

        # If sized, infer original and prefer it first
        try:
            p = urlparse(url)
            path = p.path
            if WP_SIZED_RE.search(path):
                original_path = WP_SIZED_RE.sub("", path)
                original = urlunparse(p._replace(path=original_path))
                if self._is_supported_image(original) and original not in out:
                    out.append(original)
        except Exception:
            pass

        if url not in out:
            out.append(url)

    def _is_supported_image(self, url: str) -> bool:
        try:
            ext = Path(urlparse(url).path).suffix.lower()
            return ext in SUPPORTED_EXTENSIONS
        except Exception:
            return False
