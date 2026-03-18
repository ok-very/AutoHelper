"""
Default site adapter for generic HTML pages.

Uses standard HTML extraction logic as a fallback for unknown sites.
"""

from typing import TYPE_CHECKING

from ..extractors import extract_bio_text, extract_image_urls
from .base import SiteAdapter, SiteMatch

if TYPE_CHECKING:
    from bs4 import BeautifulSoup


class DefaultAdapter(SiteAdapter):
    """
    Generic HTML adapter using standard extraction logic.

    Acts as a fallback when no site-specific adapter matches.
    """

    @property
    def name(self) -> str:
        return "default"

    @property
    def patterns(self) -> list[str]:
        return ["*"]  # Matches everything

    def detect(self, url: str, html: str) -> SiteMatch | None:
        # Always matches with low confidence as fallback
        return SiteMatch("default", 0.1, {})

    async def extract_pages(self, soup: "BeautifulSoup", base_url: str) -> list[str]:
        # Single-page extraction by default
        return []

    async def extract_images(self, soup: "BeautifulSoup", base_url: str) -> list[str]:
        # Use existing extraction logic from extractors module
        return extract_image_urls(soup, base_url)

    async def extract_bio(self, soup: "BeautifulSoup") -> str | None:
        # Use existing bio extraction logic
        return extract_bio_text(soup)
