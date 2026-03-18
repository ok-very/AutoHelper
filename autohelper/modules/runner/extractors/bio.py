"""
Bio/about text extraction from HTML.

Extracts likely bio or about text from parsed HTML using common selectors.
"""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

# CSS selectors for common bio/about containers
BIO_SELECTORS = [
    "article",
    ".bio",
    ".about",
    ".artist-bio",
    ".biography",
    "#bio",
    "#about",
    "#artist-bio",
    "#biography",
    "[class*='bio']",
    "[class*='about']",
    "main p",
]

# Minimum text length to consider as substantial content
MIN_TEXT_LENGTH = 100

# Maximum number of sections to include
MAX_SECTIONS = 5


def extract_bio_text(soup: "BeautifulSoup") -> str:
    """
    Extract likely bio/about text from parsed HTML.

    Searches for common bio containers and extracts substantial text content,
    deduplicating and joining multiple sections.

    Args:
        soup: BeautifulSoup parsed HTML document

    Returns:
        Extracted bio text with sections separated by horizontal rules,
        or empty string if no bio content found
    """
    text_parts = []

    for selector in BIO_SELECTORS:
        elements = soup.select(selector)
        for el in elements:
            text = el.get_text(separator="\n", strip=True)
            if len(text) > MIN_TEXT_LENGTH:
                text_parts.append(text)

    # Deduplicate while preserving order
    seen = set()
    unique_parts = []
    for part in text_parts:
        # Normalize for comparison (first 200 chars, collapsed whitespace)
        normalized = re.sub(r"\s+", " ", part)[:200]
        if normalized not in seen:
            seen.add(normalized)
            unique_parts.append(part)

    return "\n\n---\n\n".join(unique_parts[:MAX_SECTIONS])
