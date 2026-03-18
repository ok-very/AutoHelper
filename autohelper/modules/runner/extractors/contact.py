"""
Contact information extraction from HTML.

Cross-platform heuristics for email, phone, and location extraction.
"""

import re
from typing import TYPE_CHECKING, Union
from urllib.parse import unquote

from bs4 import BeautifulSoup
from bs4.element import Tag

if TYPE_CHECKING:
    pass

# Type alias for elements that support find_all and get_text
SoupElement = Union[BeautifulSoup, Tag]


def _get_str_attr(tag: "Tag", attr: str, default: str = "") -> str:
    """Safely get string attribute from BS4 tag (handles list returns)."""
    val = tag.get(attr)
    if val is None:
        return default
    if isinstance(val, list):
        return val[0] if val else default
    return val

# Email regex - conservative to avoid false positives
EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)

# Phone patterns - conservative to minimize false positives
PHONE_PATTERNS = [
    # International format: +1 234 567 8901
    re.compile(r"\+\d{1,3}[\s.-]?\d{2,4}[\s.-]?\d{3,4}[\s.-]?\d{3,4}"),
    # North American: (123) 456-7890 or 123-456-7890
    re.compile(r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}"),
    # European: common formats
    re.compile(r"\+\d{2}[\s.]?\d{2}[\s.]?\d{3}[\s.]?\d{2}[\s.]?\d{2}"),
]

# Location selectors - site-specific blocks
LOCATION_SELECTORS = [
    ".location",
    ".workspace",
    ".based-in",
    ".city",
    "[class*='location']",
    "[class*='workspace']",
    "[data-location]",
]

# Common city/country patterns
CITY_COUNTRY_PATTERN = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*,\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b"
)


def extract_emails(soup: SoupElement | None) -> list[str]:
    """
    Extract email addresses from HTML.

    Sources:
    1. mailto: links (primary, most reliable)
    2. Visible text content (regex scan)

    Args:
        soup: BeautifulSoup document or Tag element

    Returns:
        Deduplicated list of email addresses (empty if soup is None)
    """
    if soup is None:
        return []

    emails: list[str] = []

    # 1. Extract from mailto: links
    for link in soup.find_all("a", href=True):
        href = _get_str_attr(link, "href")
        if href.lower().startswith("mailto:"):
            # Remove mailto: prefix and any query params (?subject=...)
            mailto_content = href[7:].split("?")[0].strip()
            mailto_content = unquote(mailto_content)  # Handle URL-encoded characters
            # Handle display names like "John Doe" <john@example.com> and multiple recipients
            for match in EMAIL_PATTERN.finditer(mailto_content):
                email = match.group(0).lower()
                if email not in emails:
                    emails.append(email)

    # 2. Scan visible text for email patterns
    text = soup.get_text(separator=" ", strip=True)
    for match in EMAIL_PATTERN.finditer(text):
        email = match.group(0).lower()
        if email not in emails:
            emails.append(email)

    return list(dict.fromkeys(emails))  # Preserve order, dedupe


def extract_phones(soup: SoupElement | None) -> list[str]:
    """
    Extract phone numbers from HTML.

    Sources:
    1. tel: links (primary, most reliable)
    2. Visible text content (regex scan, conservative)

    Args:
        soup: BeautifulSoup document or Tag element

    Returns:
        Deduplicated list of phone numbers (empty if soup is None)
    """
    if soup is None:
        return []

    phones: list[str] = []

    # 1. Extract from tel: links
    for link in soup.find_all("a", href=True):
        href = _get_str_attr(link, "href")
        if href.lower().startswith("tel:"):
            phone = href[4:].strip()
            phone = unquote(phone)
            normalized = _normalize_phone(phone)
            # Validate: must have at least 7 digits (shortest valid phone numbers)
            if normalized and len(normalized) >= 7 and normalized not in phones:
                phones.append(normalized)

    # 2. Scan visible text for phone patterns
    text = soup.get_text(separator=" ", strip=True)
    for pattern in PHONE_PATTERNS:
        for match in pattern.finditer(text):
            phone = _normalize_phone(match.group(0))
            if phone not in phones and len(phone) >= 10:
                phones.append(phone)

    return list(dict.fromkeys(phones))  # Preserve order, dedupe


def _normalize_phone(phone: str) -> str:
    """Normalize phone number to consistent format."""
    # Remove common separators, keep + prefix
    cleaned = re.sub(r"[\s.\-()]+", "", phone)
    return cleaned


def extract_location(
    soup: SoupElement | None, bio_text: str | None = None
) -> tuple[str | None, list[str]]:
    """
    Extract location from HTML.

    Strategy:
    1. Check for explicit location containers (site-specific)
    2. Parse "City, Country" pattern from bio text
    3. Fallback to page-wide pattern search

    Args:
        soup: Parsed HTML document (can be None)
        bio_text: Optional bio text (if already extracted)

    Returns:
        Tuple of (best_location, all_candidates)
    """
    candidates: list[str] = []

    # Handle None soup - can still extract from bio_text
    if soup is None:
        if bio_text:
            for match in CITY_COUNTRY_PATTERN.finditer(bio_text):
                location = f"{match.group(1)}, {match.group(2)}"
                if location not in candidates:
                    candidates.append(location)
        return (candidates[0] if candidates else None, candidates)

    # 1. Check explicit location elements
    for selector in LOCATION_SELECTORS:
        for el in soup.select(selector):
            text = el.get_text(strip=True)
            if text and len(text) < 100:  # Avoid grabbing entire sections
                candidates.append(text)

    # 2. Parse "City, Country" from bio text
    if bio_text:
        for match in CITY_COUNTRY_PATTERN.finditer(bio_text):
            location = f"{match.group(1)}, {match.group(2)}"
            if location not in candidates:
                candidates.append(location)

    # 3. Also check page-wide for patterns if no candidates yet
    if not candidates:
        page_text = soup.get_text(separator=" ", strip=True)[:2000]  # First 2000 chars
        for match in CITY_COUNTRY_PATTERN.finditer(page_text):
            location = f"{match.group(1)}, {match.group(2)}"
            if location not in candidates:
                candidates.append(location)

    # Return first candidate as best guess, plus all candidates for review
    return (candidates[0] if candidates else None, candidates)
