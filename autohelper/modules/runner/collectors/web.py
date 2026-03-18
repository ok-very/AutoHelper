"""
Web collector for scraping images and content from URLs.

Collects artifacts from web pages with SSRF protection and manifest tracking.
"""

import asyncio
import logging
import mimetypes
import threading
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from ..adapters import AdapterRegistry
from ..naming import (
    IndexCounter,
    compute_content_hash,
    compute_url_hash,
    generate_filename,
    generate_persistent_id,
)
from ..ssrf import SSRFProtectedClient, is_safe_url
from ..types import (
    ArtifactManifestEntry,
    ArtifactRef,
    CollectionManifest,
    ExtractedMetadata,
    NamingConfig,
    RunnerProgress,
    RunnerResult,
)
from .base import MAX_IMAGES, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

# Lazy imports for optional dependencies
_bs4: type[BeautifulSoup] | None = None
_bs4_lock = threading.Lock()


def _get_bs4() -> type[BeautifulSoup]:
    """Lazy import BeautifulSoup (thread-safe)."""
    global _bs4
    if _bs4 is None:
        with _bs4_lock:
            # Double-check after acquiring lock
            if _bs4 is None:
                try:
                    from bs4 import BeautifulSoup as BS4Class

                    _bs4 = BS4Class
                except ImportError as e:
                    raise ImportError(
                        "beautifulsoup4 is required for web collection. "
                        "Install with: pip install beautifulsoup4 lxml"
                    ) from e
    return _bs4


def _get_html_parser() -> str:
    """Determine the best available HTML parser, with fallback."""
    try:
        import lxml  # noqa: F401

        return "lxml"
    except ImportError:
        logger.info("lxml not available, falling back to html.parser")
        return "html.parser"


class WebCollector:
    """
    Collector for web-based artifact sources.

    Downloads images and extracts text content from web pages,
    with SSRF protection and manifest tracking.
    """

    def __init__(
        self,
        timeout: float = REQUEST_TIMEOUT,
        max_images: int = MAX_IMAGES,
        min_width: int = 100,
        max_width: int = 5000,
        min_height: int = 100,
        max_height: int = 5000,
        min_filesize_kb: int = 100,
        max_filesize_kb: int = 12000,
    ):
        """
        Initialize the web collector.

        Args:
            timeout: Request timeout in seconds
            max_images: Maximum images to collect per page
            min_width: Minimum image width in pixels
            max_width: Maximum image width in pixels
            min_height: Minimum image height in pixels
            max_height: Maximum image height in pixels
            min_filesize_kb: Minimum file size in KB
            max_filesize_kb: Maximum file size in KB
        """
        self.timeout = timeout
        self.max_images = max(1, max_images)

        # Validate and normalize dimension ranges
        min_width = max(0, min_width)
        max_width = max(0, max_width)
        min_height = max(0, min_height)
        max_height = max(0, max_height)

        # Swap if min > max
        if min_width > max_width:
            min_width, max_width = max_width, min_width
        if min_height > max_height:
            min_height, max_height = max_height, min_height

        self.min_width = min_width
        self.max_width = max_width
        self.min_height = min_height
        self.max_height = max_height

        # Validate and normalize filesize ranges
        min_filesize_kb = max(0, min_filesize_kb)
        max_filesize_kb = max(0, max_filesize_kb)
        if min_filesize_kb > max_filesize_kb:
            min_filesize_kb, max_filesize_kb = max_filesize_kb, min_filesize_kb

        self.min_filesize_bytes = min_filesize_kb * 1024
        self.max_filesize_bytes = max_filesize_kb * 1024

    async def collect(
        self,
        source: str,
        output_folder: Path,
        naming_config: NamingConfig,
        context_id: str | None = None,
    ) -> RunnerResult:
        """
        Collect artifacts from a web URL.

        Args:
            source: Web URL to collect from
            output_folder: Output folder for artifacts
            naming_config: Configuration for artifact naming
            context_id: Optional context identifier

        Returns:
            RunnerResult with collection outcome
        """
        # Validate URL for SSRF protection
        is_safe, error_msg = await is_safe_url(source)
        if not is_safe:
            return RunnerResult(
                success=False,
                error=f"URL validation failed: {error_msg}",
            )

        BS4 = _get_bs4()
        artifacts: list[ArtifactRef] = []
        manifest_entries: list[ArtifactManifestEntry] = []
        now = datetime.now(UTC).isoformat()

        try:
            # Ensure output folder exists
            output_folder.mkdir(parents=True, exist_ok=True)

            # Initialize index counter
            counter = IndexCounter(
                start=naming_config.index_start,
                mode=naming_config.numbering_mode,
            )

            # Fetch the page
            client = SSRFProtectedClient(timeout=self.timeout)
            response = await client.get(source)
            response.raise_for_status()
            html = response.text

            # Parse HTML
            soup = BS4(html, _get_html_parser())

            # Detect site type and get appropriate adapter
            adapter, match = AdapterRegistry.detect(source, html)
            logger.info(f"Detected site type: {adapter.name} (confidence: {match.confidence})")

            # Extract bio text using adapter
            bio_text = await adapter.extract_bio(soup)
            if bio_text:
                bio_path = output_folder / "bio.txt"
                await asyncio.to_thread(bio_path.write_text, bio_text, encoding="utf-8")
                bio_ref_id = await asyncio.to_thread(lambda: str(uuid.uuid4()))
                artifacts.append(
                    ArtifactRef(
                        ref_id=bio_ref_id,
                        path=str(bio_path),
                        artifact_type="text",
                        mime_type="text/plain",
                    )
                )

            # Extract metadata (contact info, CV links, location)
            extracted_metadata = await adapter.extract_metadata(soup, source, bio_text)
            logger.info(
                f"Extracted metadata: {len(extracted_metadata.emails)} emails, "
                f"{len(extracted_metadata.phones)} phones, "
                f"{len(extracted_metadata.cv_links)} CV links, "
                f"location: {extracted_metadata.location}"
            )

            # Extract sub-pages (for multi-page sites like Cargo)
            all_pages: list[tuple[str, BeautifulSoup]] = [(source, soup)]
            page_urls = await adapter.extract_pages(soup, source)

            for page_url in page_urls[:10]:  # Limit sub-pages
                try:
                    is_page_safe, _ = await is_safe_url(page_url)
                    if not is_page_safe:
                        continue
                    page_response = await client.get(page_url)
                    page_response.raise_for_status()
                    page_soup = BS4(page_response.text, _get_html_parser())
                    all_pages.append((page_url, page_soup))
                except Exception as e:
                    logger.warning(f"Failed to fetch sub-page {page_url}: {e}")

            # Extract images from all pages using adapter
            image_urls: list[str] = []
            for page_url, page_soup in all_pages:
                page_images = await adapter.extract_images(page_soup, page_url)
                image_urls.extend(page_images)

            # Deduplicate while preserving order
            image_urls = list(dict.fromkeys(image_urls))
            logger.info(f"Found {len(image_urls)} images across {len(all_pages)} pages")

            for img_url in image_urls[: self.max_images]:
                result = await self._download_image(
                    img_url,
                    output_folder,
                    counter,
                    naming_config,
                    source,
                    now,
                )
                if result:
                    artifact, entry = result
                    artifacts.append(artifact)
                    manifest_entries.append(entry)

            # Download CV/resume PDFs
            if extracted_metadata.cv_links:
                cv_results = await self._download_cv_pdfs(
                    extracted_metadata.cv_links,
                    output_folder,
                    counter,
                    source,
                    now,
                )
                for artifact, entry in cv_results:
                    artifacts.append(artifact)
                    manifest_entries.append(entry)

            # Save manifest with extracted metadata
            await self._save_manifest(
                output_folder, source, naming_config, manifest_entries, now, extracted_metadata
            )

            return RunnerResult(success=True, artifacts=artifacts)

        except Exception as e:
            logger.exception(f"Web collection failed for {source}")
            return RunnerResult(success=False, error=str(e), artifacts=artifacts)

    async def collect_stream(
        self,
        source: str,
        output_folder: Path,
        naming_config: NamingConfig,
        context_id: str | None = None,
    ) -> AsyncIterator[RunnerProgress]:
        """
        Collect from web with streaming progress.

        Args:
            source: Web URL to collect from
            output_folder: Output folder for artifacts
            naming_config: Configuration for artifact naming
            context_id: Optional context identifier

        Yields:
            RunnerProgress events during collection
        """
        # Validate URL for SSRF protection
        is_safe, error_msg = await is_safe_url(source)
        if not is_safe:
            yield RunnerProgress(stage="error", message=f"URL validation failed: {error_msg}")
            return

        BS4 = _get_bs4()
        manifest_entries: list[ArtifactManifestEntry] = []
        now = datetime.now(UTC).isoformat()

        yield RunnerProgress(stage="connecting", message=f"Fetching {source}...", percent=5)

        try:
            output_folder.mkdir(parents=True, exist_ok=True)

            # Initialize index counter
            counter = IndexCounter(
                start=naming_config.index_start,
                mode=naming_config.numbering_mode,
            )

            # Fetch the page
            client = SSRFProtectedClient(timeout=self.timeout)
            response = await client.get(source)
            response.raise_for_status()
            html = response.text

            yield RunnerProgress(stage="parsing", message="Parsing page content...", percent=15)

            soup = BS4(html, _get_html_parser())

            # Detect site type and get appropriate adapter
            adapter, match = AdapterRegistry.detect(source, html)
            logger.info(f"Detected site type: {adapter.name} (confidence: {match.confidence})")

            yield RunnerProgress(
                stage="detecting",
                message=f"Detected site type: {adapter.name}",
                percent=20,
            )

            # Extract bio using adapter
            bio_text = await adapter.extract_bio(soup)
            if bio_text:
                bio_path = output_folder / "bio.txt"
                await asyncio.to_thread(bio_path.write_text, bio_text, encoding="utf-8")
                yield RunnerProgress(stage="bio", message="Extracted bio text", percent=23)

            # Extract metadata (contact info, CV links, location)
            extracted_metadata = await adapter.extract_metadata(soup, source, bio_text)
            metadata_msg = []
            if extracted_metadata.emails:
                metadata_msg.append(f"{len(extracted_metadata.emails)} emails")
            if extracted_metadata.phones:
                metadata_msg.append(f"{len(extracted_metadata.phones)} phones")
            if extracted_metadata.cv_links:
                metadata_msg.append(f"{len(extracted_metadata.cv_links)} CVs")
            if extracted_metadata.location:
                metadata_msg.append(f"location: {extracted_metadata.location}")

            if metadata_msg:
                yield RunnerProgress(
                    stage="metadata",
                    message=f"Found {', '.join(metadata_msg)}",
                    percent=25,
                )

            # Extract sub-pages (for multi-page sites)
            all_pages: list[tuple[str, BeautifulSoup]] = [(source, soup)]
            page_urls = await adapter.extract_pages(soup, source)

            if page_urls:
                yield RunnerProgress(
                    stage="pages",
                    message=f"Found {len(page_urls)} sub-pages to crawl",
                    percent=28,
                )

            for page_url in page_urls[:10]:  # Limit sub-pages
                try:
                    is_page_safe, _ = await is_safe_url(page_url)
                    if not is_page_safe:
                        continue
                    page_response = await client.get(page_url)
                    page_response.raise_for_status()
                    page_soup = BS4(page_response.text, _get_html_parser())
                    all_pages.append((page_url, page_soup))
                except Exception as e:
                    logger.warning(f"Failed to fetch sub-page {page_url}: {e}")

            # Extract images from all pages using adapter
            image_urls: list[str] = []
            for page_url, page_soup in all_pages:
                page_images = await adapter.extract_images(page_soup, page_url)
                image_urls.extend(page_images)

            # Deduplicate while preserving order
            image_urls = list(dict.fromkeys(image_urls))
            total_images = min(len(image_urls), self.max_images)

            yield RunnerProgress(
                stage="images",
                message=f"Found {total_images} images to download",
                percent=35,
            )

            # Download images with progress
            if total_images > 0:
                for i, img_url in enumerate(image_urls[: self.max_images]):
                    try:
                        result = await self._download_image(
                            img_url,
                            output_folder,
                            counter,
                            naming_config,
                            source,
                            now,
                        )
                        if result:
                            _, entry = result
                            manifest_entries.append(entry)

                        progress = 35 + int((i + 1) / total_images * 55)
                        yield RunnerProgress(
                            stage="downloading",
                            message=f"Downloaded image {i + 1}/{total_images}",
                            percent=progress,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to download {img_url}: {e}")

            # Download CV/resume PDFs
            if extracted_metadata.cv_links:
                yield RunnerProgress(
                    stage="documents",
                    message=f"Downloading {len(extracted_metadata.cv_links)} CV/resume PDFs...",
                    percent=92,
                )
                cv_results = await self._download_cv_pdfs(
                    extracted_metadata.cv_links,
                    output_folder,
                    counter,
                    source,
                    now,
                )
                for _, entry in cv_results:
                    manifest_entries.append(entry)

            # Save manifest with extracted metadata
            await self._save_manifest(
                output_folder, source, naming_config, manifest_entries, now, extracted_metadata
            )

            yield RunnerProgress(stage="complete", message="Collection complete!", percent=100)

        except Exception as e:
            yield RunnerProgress(stage="error", message=str(e))

    async def _download_image(
        self,
        url: str,
        output_folder: Path,
        counter: IndexCounter,
        naming_config: NamingConfig,
        source_url: str,
        timestamp: str,
    ) -> tuple[ArtifactRef, ArtifactManifestEntry] | None:
        """
        Download a single image with naming and manifest entry creation.

        Returns:
            Tuple of (ArtifactRef, ArtifactManifestEntry) or None if failed
        """
        # Validate URL for SSRF protection
        is_safe, error_msg = await is_safe_url(url)
        if not is_safe:
            logger.warning(f"Skipping unsafe image URL {url}: {error_msg}")
            return None

        try:
            client = SSRFProtectedClient(timeout=self.timeout)
            response = await client.get(url)
            response.raise_for_status()

            # Check Content-Length header before processing (memory protection)
            content_length = response.headers.get("content-length")
            if content_length:
                try:
                    size = int(content_length)
                    if size > self.max_filesize_bytes:
                        logger.debug(f"Skipping image {url}: Content-Length {size} > max {self.max_filesize_bytes}")
                        return None
                except ValueError:
                    pass  # Invalid Content-Length header, continue with download

            content = response.content

            # Validate content-type
            content_type = response.headers.get("content-type", "")
            content_type_base = content_type.split(";")[0].strip().lower()
            if not content_type_base.startswith("image/"):
                logger.warning(f"Skipping non-image content-type {content_type_base} from {url}")
                return None

            ext = mimetypes.guess_extension(content_type_base) or ".jpg"

            # Check filesize bounds
            file_size = len(content)
            if file_size < self.min_filesize_bytes:
                logger.debug(f"Skipping image {url}: size {file_size} < min {self.min_filesize_bytes}")
                return None
            if file_size > self.max_filesize_bytes:
                logger.debug(f"Skipping image {url}: size {file_size} > max {self.max_filesize_bytes}")
                return None

            # Check image dimensions
            try:
                from PIL import Image
                import io
                with Image.open(io.BytesIO(content)) as img:
                    width, height = img.size
                    if width < self.min_width or width > self.max_width:
                        logger.debug(f"Skipping image {url}: width {width} outside [{self.min_width}, {self.max_width}]")
                        return None
                    if height < self.min_height or height > self.max_height:
                        logger.debug(f"Skipping image {url}: height {height} outside [{self.min_height}, {self.max_height}]")
                        return None
            except Exception as e:
                logger.warning(f"Could not read image dimensions for {url}: {e}")
                # Continue anyway - dimension check is best-effort

            # Build context for filename generation
            context = {
                "source_url": source_url,
                "url_hash": compute_url_hash(url),
                "content_hash": compute_content_hash(content),
                "timestamp": timestamp,
            }

            # Generate filename using naming config
            index = counter.next(source_key=source_url)
            filename = generate_filename(naming_config, context, index, ext)
            filepath = output_folder / filename

            # Write file
            await asyncio.to_thread(filepath.write_bytes, content)

            # Generate persistent ID
            artifact_id = generate_persistent_id(content, url, timestamp)

            # Create artifact reference
            artifact = ArtifactRef(
                ref_id=artifact_id,
                path=str(filepath),
                artifact_type="image",
                mime_type=content_type_base or "image/jpeg",
            )

            # Create manifest entry
            entry = ArtifactManifestEntry(
                artifact_id=artifact_id,
                original_filename=filename,
                current_filename=filename,
                content_hash=context["content_hash"],
                source_url=url,
                collected_at=timestamp,
                mime_type=content_type_base or "image/jpeg",
                size=len(content),
                metadata={
                    "source_page": source_url,
                    "url_hash": context["url_hash"],
                },
            )

            return artifact, entry

        except ValueError as e:
            logger.warning(f"Image URL blocked by SSRF protection {url}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Failed to download image {url}: {e}")
            return None

    async def _download_cv_pdfs(
        self,
        cv_links: list[str],
        output_folder: Path,
        counter: IndexCounter,
        source_url: str,
        timestamp: str,
    ) -> list[tuple[ArtifactRef, ArtifactManifestEntry]]:
        """
        Download CV/resume PDFs and create manifest entries.

        Args:
            cv_links: List of PDF URLs to download
            output_folder: Output folder for artifacts
            counter: Index counter for naming
            source_url: Source page URL
            timestamp: Collection timestamp

        Returns:
            List of (ArtifactRef, ArtifactManifestEntry) tuples
        """
        results: list[tuple[ArtifactRef, ArtifactManifestEntry]] = []

        for url in cv_links:
            # SSRF validation
            is_safe, error_msg = await is_safe_url(url)
            if not is_safe:
                logger.warning(f"Skipping unsafe CV URL {url}: {error_msg}")
                continue

            try:
                client = SSRFProtectedClient(timeout=self.timeout)
                response = await client.get(url)
                response.raise_for_status()
                content = response.content

                # Validate content-type
                content_type = response.headers.get("content-type", "")
                content_type_base = content_type.split(";")[0].strip().lower()
                if "pdf" not in content_type_base:
                    logger.warning(f"Skipping non-PDF content-type {content_type_base} from {url}")
                    continue

                # Generate filename (cv_001.pdf, cv_002.pdf, etc.)
                index = counter.next(source_key="cv")
                filename = f"cv_{index:03d}.pdf"
                filepath = output_folder / filename

                # Write file
                await asyncio.to_thread(filepath.write_bytes, content)

                # Extract text from PDF for metadata
                from ..extractors.text import extract_pdf_text

                extracted_text = await asyncio.to_thread(extract_pdf_text, filepath)

                # Generate persistent ID
                content_hash = compute_content_hash(content)
                artifact_id = generate_persistent_id(content, url, timestamp)

                artifact = ArtifactRef(
                    ref_id=artifact_id,
                    path=str(filepath),
                    artifact_type="document",
                    mime_type="application/pdf",
                )

                entry = ArtifactManifestEntry(
                    artifact_id=artifact_id,
                    original_filename=filename,
                    current_filename=filename,
                    content_hash=content_hash,
                    source_url=url,
                    collected_at=timestamp,
                    mime_type="application/pdf",
                    size=len(content),
                    metadata={
                        "document_type": "cv",
                        "source_page": source_url,
                        "extracted_text": extracted_text,
                    },
                )

                results.append((artifact, entry))
                logger.info(f"Downloaded CV: {filename} from {url}")

            except Exception as e:
                logger.warning(f"Failed to download CV {url}: {e}")

        return results

    async def _save_manifest(
        self,
        output_folder: Path,
        source_url: str,
        naming_config: NamingConfig,
        entries: list[ArtifactManifestEntry],
        timestamp: str,
        extracted_metadata: ExtractedMetadata | None = None,
    ) -> None:
        """Save collection manifest to output folder."""
        from ...storage import get_metadata_backend

        # Generate UUID in thread to avoid blocking event loop on entropy reads
        manifest_id = await asyncio.to_thread(lambda: str(uuid.uuid4()))

        manifest = CollectionManifest(
            manifest_id=manifest_id,
            created_at=timestamp,
            updated_at=timestamp,
            source_type="web",
            source_url=source_url,
            output_folder=str(output_folder),
            naming_config=naming_config,
            artifacts=entries,
            extracted_metadata=extracted_metadata,
        )

        backend = get_metadata_backend(output_folder)
        await backend.save_collection(manifest)
