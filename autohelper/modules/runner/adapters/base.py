"""
Site adapter base class and types.

Provides the foundation for site-specific scraping strategies.
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..types import ExtractedMetadata

if TYPE_CHECKING:
    from bs4 import BeautifulSoup


@dataclass
class SiteMatch:
    """Result of site detection."""

    adapter_name: str
    confidence: float  # 0-1, higher = better match
    metadata: dict[str, Any] = field(default_factory=dict)


class SiteAdapter(ABC):
    """
    Base class for site-specific scrapers.

    Subclasses implement detection and extraction logic for specific
    site platforms (Cargo, Squarespace, etc.).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Adapter identifier (e.g., 'cargo', 'squarespace')."""

    @property
    @abstractmethod
    def patterns(self) -> list[str]:
        """URL/HTML patterns this adapter handles."""

    @abstractmethod
    def detect(self, url: str, html: str) -> SiteMatch | None:
        """
        Check if this adapter should handle the site.

        Args:
            url: The page URL
            html: Raw HTML content

        Returns:
            SiteMatch if this adapter can handle the site, None otherwise
        """

    @abstractmethod
    async def extract_pages(self, soup: "BeautifulSoup", base_url: str) -> list[str]:
        """
        Extract sub-page URLs to crawl (for multi-page sites).

        Args:
            soup: Parsed HTML document
            base_url: Base URL for resolving relative URLs

        Returns:
            List of absolute URLs to crawl
        """

    @abstractmethod
    async def extract_images(self, soup: "BeautifulSoup", base_url: str) -> list[str]:
        """
        Extract image URLs from a page.

        Args:
            soup: Parsed HTML document
            base_url: Base URL for resolving relative URLs

        Returns:
            List of absolute image URLs
        """

    async def extract_bio(self, soup: "BeautifulSoup") -> str | None:
        """
        Extract bio/about text from the page.

        Override in subclasses for site-specific bio extraction.

        Args:
            soup: Parsed HTML document

        Returns:
            Bio text or None if not found
        """
        return None

    async def extract_metadata(
        self, soup: "BeautifulSoup", base_url: str, bio_text: str | None = None
    ) -> ExtractedMetadata:
        """
        Extract contact info and metadata from page.

        Default implementation uses cross-platform extractors.
        Site-specific adapters can override for custom extraction.

        Args:
            soup: Parsed HTML document
            base_url: Base URL for resolving relative URLs
            bio_text: Optional bio text (if already extracted)

        Returns:
            ExtractedMetadata with emails, phones, cv_links, location
        """
        # Run CPU-bound HTML processing in thread to avoid blocking event loop
        return await asyncio.to_thread(
            self._extract_metadata_sync, soup, base_url, bio_text
        )

    def _extract_metadata_sync(
        self, soup: "BeautifulSoup", base_url: str, bio_text: str | None
    ) -> ExtractedMetadata:
        """Synchronous implementation of metadata extraction."""
        from ..extractors.contact import extract_emails, extract_location, extract_phones
        from ..extractors.documents import extract_cv_links

        emails = extract_emails(soup)
        phones = extract_phones(soup)
        cv_links = extract_cv_links(soup, base_url)
        location, location_candidates = extract_location(soup, bio_text)

        return ExtractedMetadata(
            emails=emails,
            phones=phones,
            cv_links=cv_links,
            location=location,
            raw_location_candidates=location_candidates,
        )
