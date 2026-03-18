"""
Folder collector for local filesystem intake.

Collects artifacts from local folders with symlink safety and manifest tracking.
"""

import asyncio
import logging
import mimetypes
import shutil
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

from ..naming import (
    IndexCounter,
    compute_content_hash_streaming,
    generate_filename,
    generate_persistent_id_from_hash,
)
from ..types import (
    ArtifactManifestEntry,
    ArtifactRef,
    CollectionManifest,
    NamingConfig,
    RunnerProgress,
    RunnerResult,
)
from .base import (
    get_artifact_type,
    scan_files_safe,
)

logger = logging.getLogger(__name__)


class FolderCollector:
    """
    Collector for local filesystem sources.

    Scans local folders for files, copies them to the output folder,
    and creates manifest entries for tracking.
    """

    def __init__(self) -> None:
        """Initialize the folder collector."""
        pass

    async def collect(
        self,
        source: str,
        output_folder: Path,
        naming_config: NamingConfig,
        context_id: str | None = None,
    ) -> RunnerResult:
        """
        Collect artifacts from a local folder.

        Args:
            source: Local folder path
            output_folder: Output folder for artifacts
            naming_config: Configuration for artifact naming
            context_id: Optional context identifier

        Returns:
            RunnerResult with collection outcome
        """
        source_path = Path(source)

        # Validate source path
        exists = await asyncio.to_thread(source_path.exists)
        if not exists:
            return RunnerResult(
                success=False,
                error=f"Source path does not exist: {source_path}",
            )

        is_dir = await asyncio.to_thread(source_path.is_dir)
        if not is_dir:
            return RunnerResult(
                success=False,
                error=f"Source path is not a directory: {source_path}",
            )

        artifacts: list[ArtifactRef] = []
        manifest_entries: list[ArtifactManifestEntry] = []
        now = datetime.now(UTC).isoformat()

        try:
            # Ensure output folder exists
            await asyncio.to_thread(output_folder.mkdir, parents=True, exist_ok=True)

            # Initialize index counter
            counter = IndexCounter(
                start=naming_config.index_start,
                mode=naming_config.numbering_mode,
            )

            # Scan files safely
            resolved_source = await asyncio.to_thread(source_path.resolve)
            files = await scan_files_safe(source_path)

            for item in files:
                result = await self._process_file(
                    item,
                    resolved_source,
                    output_folder,
                    counter,
                    naming_config,
                    now,
                )
                if result:
                    artifact, entry = result
                    artifacts.append(artifact)
                    manifest_entries.append(entry)

            # Save manifest with resolved source path for consistency
            await self._save_manifest(
                output_folder, str(resolved_source), naming_config, manifest_entries, now
            )

            return RunnerResult(success=True, artifacts=artifacts)

        except Exception as e:
            logger.exception(f"Folder collection failed for {source_path}")
            return RunnerResult(success=False, error=str(e), artifacts=artifacts)

    async def collect_stream(
        self,
        source: str,
        output_folder: Path,
        naming_config: NamingConfig,
        context_id: str | None = None,
    ) -> AsyncIterator[RunnerProgress]:
        """
        Collect from folder with streaming progress.

        Args:
            source: Local folder path
            output_folder: Output folder for artifacts
            naming_config: Configuration for artifact naming
            context_id: Optional context identifier

        Yields:
            RunnerProgress events during collection
        """
        source_path = Path(source)

        yield RunnerProgress(
            stage="scanning",
            message=f"Scanning {source_path}...",
            percent=10,
        )

        # Validate source path
        exists = await asyncio.to_thread(source_path.exists)
        if not exists:
            yield RunnerProgress(
                stage="error",
                message=f"Source path does not exist: {source_path}",
            )
            return

        is_dir = await asyncio.to_thread(source_path.is_dir)
        if not is_dir:
            yield RunnerProgress(
                stage="error",
                message=f"Source path is not a directory: {source_path}",
            )
            return

        manifest_entries: list[ArtifactManifestEntry] = []
        now = datetime.now(UTC).isoformat()

        try:
            # Ensure output folder exists
            await asyncio.to_thread(output_folder.mkdir, parents=True, exist_ok=True)

            # Initialize index counter
            counter = IndexCounter(
                start=naming_config.index_start,
                mode=naming_config.numbering_mode,
            )

            # Scan files safely
            resolved_source = await asyncio.to_thread(source_path.resolve)
            files = await scan_files_safe(source_path)
            total = len(files)

            yield RunnerProgress(
                stage="processing",
                message=f"Found {total} files",
                percent=30,
            )

            # Handle empty directory case
            if total == 0:
                yield RunnerProgress(
                    stage="complete",
                    message="No files found in directory",
                    percent=100,
                )
                return

            # Process files
            artifacts_collected = 0
            for i, item in enumerate(files):
                try:
                    result = await self._process_file(
                        item,
                        resolved_source,
                        output_folder,
                        counter,
                        naming_config,
                        now,
                    )
                    if result:
                        _, entry = result
                        manifest_entries.append(entry)
                        artifacts_collected += 1
                except Exception as e:
                    logger.warning(f"Failed to process {item}: {e}")

                progress = 30 + int((i + 1) / total * 65)
                if i % 10 == 0:  # Update every 10 files
                    yield RunnerProgress(
                        stage="processing",
                        message=f"Processed {i + 1}/{total} files",
                        percent=progress,
                    )
                await asyncio.sleep(0)  # Yield control

            # Save manifest with resolved source path for consistency
            await self._save_manifest(
                output_folder, str(resolved_source), naming_config, manifest_entries, now
            )

            yield RunnerProgress(
                stage="complete",
                message=f"Collected {artifacts_collected} files",
                percent=100,
            )

        except Exception as e:
            yield RunnerProgress(stage="error", message=str(e))

    async def _process_file(
        self,
        item: Path,
        resolved_source: Path,
        output_folder: Path,
        counter: IndexCounter,
        naming_config: NamingConfig,
        timestamp: str,
    ) -> tuple[ArtifactRef, ArtifactManifestEntry] | None:
        """
        Process a single file: copy and create manifest entry.

        Returns:
            Tuple of (ArtifactRef, ArtifactManifestEntry) or None if failed
        """
        try:
            # Compute content hash using streaming (memory-efficient for large files)
            content_hash = await asyncio.to_thread(compute_content_hash_streaming, item)

            # Get file metadata
            ext = item.suffix.lower()
            artifact_type = get_artifact_type(ext)
            mime_type, _ = mimetypes.guess_type(str(item))
            file_size = await asyncio.to_thread(lambda: item.stat().st_size)

            # Build context for filename generation
            context = {
                "source_path": str(resolved_source),
                "filename_stem": item.stem,
                "content_hash": content_hash,
                "timestamp": timestamp,
                "folder_name": resolved_source.name,
            }

            # Generate filename using naming config
            index = counter.next(source_key=str(resolved_source))
            filename = generate_filename(naming_config, context, index, ext)

            # Preserve relative directory structure in output
            rel_path = item.relative_to(resolved_source)
            dest_dir = output_folder / rel_path.parent
            await asyncio.to_thread(dest_dir.mkdir, parents=True, exist_ok=True)

            # For folder collection, we preserve original name in directory structure
            # but use generated name for the file itself
            dest_path = dest_dir / filename

            # Copy file
            await asyncio.to_thread(shutil.copy2, item, dest_path)

            # Generate persistent ID from pre-computed hash
            artifact_id = generate_persistent_id_from_hash(content_hash, str(item), timestamp)

            # Create artifact reference
            artifact = ArtifactRef(
                ref_id=artifact_id,
                path=str(dest_path),
                artifact_type=artifact_type,
                mime_type=mime_type,
            )

            # Create manifest entry
            entry = ArtifactManifestEntry(
                artifact_id=artifact_id,
                original_filename=item.name,
                current_filename=filename,
                content_hash=content_hash,
                source_path=str(item),
                collected_at=timestamp,
                mime_type=mime_type or "application/octet-stream",
                size=file_size,
                metadata={
                    "original_path": str(rel_path),
                    "source_folder": str(resolved_source),
                },
            )

            return artifact, entry

        except Exception as e:
            logger.warning(f"Failed to process file {item}: {e}")
            return None

    async def _save_manifest(
        self,
        output_folder: Path,
        source_path: str,
        naming_config: NamingConfig,
        entries: list[ArtifactManifestEntry],
        timestamp: str,
    ) -> None:
        """Save collection manifest to output folder."""
        from ...storage import get_metadata_backend

        manifest = CollectionManifest(
            manifest_id=str(uuid.uuid4()),
            created_at=timestamp,
            updated_at=timestamp,
            source_type="local",
            source_path=source_path,
            output_folder=str(output_folder),
            naming_config=naming_config,
            artifacts=entries,
        )

        backend = get_metadata_backend(output_folder)
        await backend.save_collection(manifest)
