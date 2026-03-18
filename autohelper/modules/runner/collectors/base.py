"""
Base collector protocol and shared utilities.

Provides the CollectorProtocol interface and shared utilities for artifact collection.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ..types import NamingConfig, RunnerProgress, RunnerResult

logger = logging.getLogger(__name__)

# Supported image file extensions
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}

# Supported document extensions
SUPPORTED_DOCUMENT_EXTENSIONS = {".txt", ".md", ".doc", ".docx", ".pdf"}

# Maximum images per collection
MAX_IMAGES = 50

# Default request timeout in seconds
REQUEST_TIMEOUT = 30.0


class CollectorProtocol(Protocol):
    """Protocol for artifact collectors."""

    async def collect(
        self,
        source: str,
        output_folder: Path,
        naming_config: "NamingConfig",
        context_id: str | None = None,
    ) -> "RunnerResult":
        """
        Collect artifacts from source.

        Args:
            source: Source URL or path
            output_folder: Output folder for collected artifacts
            naming_config: Configuration for artifact naming
            context_id: Optional context identifier

        Returns:
            RunnerResult with collection outcome
        """
        ...

    async def collect_stream(
        self,
        source: str,
        output_folder: Path,
        naming_config: "NamingConfig",
        context_id: str | None = None,
    ) -> AsyncIterator["RunnerProgress"]:
        """
        Collect with streaming progress updates.

        Args:
            source: Source URL or path
            output_folder: Output folder for collected artifacts
            naming_config: Configuration for artifact naming
            context_id: Optional context identifier

        Yields:
            RunnerProgress events during collection
        """
        ...


def get_artifact_type(extension: str) -> str:
    """
    Determine artifact type from file extension.

    Args:
        extension: File extension (with or without leading dot)

    Returns:
        Artifact type: "image", "document", or "file"
    """
    ext = extension.lower()
    if not ext.startswith("."):
        ext = f".{ext}"

    if ext in SUPPORTED_IMAGE_EXTENSIONS:
        return "image"
    elif ext in SUPPORTED_DOCUMENT_EXTENSIONS:
        return "document"
    else:
        return "file"


async def scan_files_safe(source_path: Path) -> list[Path]:
    """
    Scan directory for files with symlink safety.

    - Does not follow symlinked directories during traversal
    - Resolves symlinked files and validates targets stay within source
    - Deduplicates files (multiple symlinks to same target)
    - Skips inaccessible files gracefully

    Args:
        source_path: Directory to scan

    Returns:
        List of resolved file paths within the source directory
    """
    resolved_source = source_path.resolve()

    def _scan() -> list[Path]:
        safe_files = []
        seen_paths: set[Path] = set()
        dirs_to_scan = [resolved_source]

        while dirs_to_scan:
            current_dir = dirs_to_scan.pop()
            try:
                entries = list(current_dir.iterdir())
            except (OSError, PermissionError) as e:
                logger.warning(f"Skipping inaccessible directory {current_dir}: {e}")
                continue

            for item in entries:
                try:
                    # For directories, only recurse if not a symlink
                    if item.is_dir():
                        if not item.is_symlink():
                            dirs_to_scan.append(item)
                        else:
                            logger.debug(f"Skipping symlinked directory: {item}")
                        continue

                    if not item.is_file():
                        continue
                except (OSError, PermissionError) as e:
                    logger.warning(f"Skipping inaccessible item {item}: {e}")
                    continue

                # Resolve symlinks and verify target is within source
                try:
                    resolved_item = item.resolve()
                    # Check if resolved path is within the source directory
                    resolved_item.relative_to(resolved_source)
                    # Skip if already seen (multiple symlinks to same target)
                    if resolved_item in seen_paths:
                        continue
                    seen_paths.add(resolved_item)
                    safe_files.append(resolved_item)
                except (ValueError, OSError) as e:
                    # ValueError: Path is outside source_path (symlink escape attempt)
                    # OSError: Could not resolve path
                    logger.warning(f"Skipping file {item}: {e}")
                    continue

        return safe_files

    return await asyncio.to_thread(_scan)
