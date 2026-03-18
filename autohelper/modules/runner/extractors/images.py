"""
Image URL extraction from HTML.

Extracts image URLs from parsed HTML, including img tags and CSS background images.
"""

import re
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlparse

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

# Supported image file extensions
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}


def extract_image_urls(
    soup: "BeautifulSoup",
    base_url: str,
    supported_extensions: set[str] | None = None,
) -> list[str]:
    """
    Extract image URLs from parsed HTML.

    Searches for:
    - img tags (src, data-src, data-lazy-src attributes)
    - CSS background-image URLs in style attributes

    Args:
        soup: BeautifulSoup parsed HTML document
        base_url: Base URL for resolving relative URLs
        supported_extensions: Optional set of allowed extensions (default: common image formats)

    Returns:
        List of absolute image URLs, deduplicated while preserving order
    """
    if supported_extensions is None:
        supported_extensions = SUPPORTED_IMAGE_EXTENSIONS

    image_urls = []

    # Find all img tags
    for img in soup.find_all("img"):
        src = (
            _get_str_attr(img, "src")
            or _get_str_attr(img, "data-src")
            or _get_str_attr(img, "data-lazy-src")
        )
        if src:
            full_url = urljoin(base_url, src)
            if _is_supported_image(full_url, supported_extensions):
                image_urls.append(full_url)

    # Check for background images in style attributes
    # Regex handles: url("..."), url('...'), and url(...)
    # Uses non-greedy matching with proper delimiter awareness
    for el in soup.find_all(style=re.compile(r"background.*url")):
        style = _get_str_attr(el, "style")
        # Match url() with double quotes, single quotes, or no quotes
        # Handle each quote type separately to avoid truncation issues
        for match in re.finditer(r'url\(\s*"([^"]*)"\s*\)', style):
            full_url = urljoin(base_url, match.group(1))
            if _is_supported_image(full_url, supported_extensions):
                image_urls.append(full_url)
        for match in re.finditer(r"url\(\s*'([^']*)'\s*\)", style):
            full_url = urljoin(base_url, match.group(1))
            if _is_supported_image(full_url, supported_extensions):
                image_urls.append(full_url)
        for match in re.finditer(r'url\(\s*([^"\'\s)]+)\s*\)', style):
            full_url = urljoin(base_url, match.group(1))
            if _is_supported_image(full_url, supported_extensions):
                image_urls.append(full_url)

    # Deduplicate while preserving order
    return list(dict.fromkeys(image_urls))


def _is_supported_image(url: str, supported_extensions: set[str]) -> bool:
    """Check if URL points to a supported image type by extension."""
    try:
        parsed = urlparse(url)
        ext = Path(parsed.path).suffix.lower()
        return ext in supported_extensions
    except Exception:
        return False
