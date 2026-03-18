"""
Document link extraction from HTML.

Extracts CV/resume PDF links with keyword matching.
"""

from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import unquote, urljoin, urlparse

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

# Keywords indicating CV/resume documents (case-insensitive)
CV_KEYWORDS = {"cv", "resume", "curriculum", "vitae", "lebenslauf"}


def extract_cv_links(soup: "BeautifulSoup", base_url: str) -> list[str]:
    """
    Extract CV/resume PDF links from HTML.

    Scans all <a href> elements where:
    - href contains .pdf
    - filename OR anchor text contains cv/resume keywords

    Args:
        soup: BeautifulSoup parsed HTML document
        base_url: Base URL for resolving relative URLs

    Returns:
        List of absolute URLs to CV/resume PDFs
    """
    cv_links: list[str] = []

    for link in soup.find_all("a", href=True):
        href = _get_str_attr(link, "href")

        # Must be a PDF link
        if ".pdf" not in href.lower():
            continue

        # Resolve to absolute URL
        full_url = urljoin(base_url, href)

        # Check filename for CV keywords
        try:
            parsed = urlparse(full_url)
            filename = unquote(Path(parsed.path).name).lower()
        except Exception:
            filename = ""

        # Check anchor text for CV keywords
        anchor_text = link.get_text(strip=True).lower()

        # Match if keywords found in filename or anchor text
        has_cv_keyword = any(kw in filename or kw in anchor_text for kw in CV_KEYWORDS)

        if has_cv_keyword and full_url not in cv_links:
            cv_links.append(full_url)

    return cv_links


def extract_pdf_links(soup: "BeautifulSoup", base_url: str) -> list[str]:
    """
    Extract all PDF links from HTML (not just CV).

    Args:
        soup: BeautifulSoup parsed HTML document
        base_url: Base URL for resolving relative URLs

    Returns:
        List of absolute URLs to PDF files
    """
    pdf_links: list[str] = []

    for link in soup.find_all("a", href=True):
        href = _get_str_attr(link, "href")
        if ".pdf" in href.lower():
            full_url = urljoin(base_url, href)
            if full_url not in pdf_links:
                pdf_links.append(full_url)

    return pdf_links
