"""
JSON Manifest storage backend (default).

Stores artifact metadata in a local JSON file at:
{output_folder}/.artcollector/manifest.json
"""

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from ..runner.types import (
    ArtifactManifestEntry,
    CollectionManifest,
)

logger = logging.getLogger(__name__)

# Manifest directory name (hidden folder)
MANIFEST_DIR = ".artcollector"
MANIFEST_FILE = "manifest.json"


class ManifestStorageBackend:
    """
    JSON manifest-based metadata storage (default backend).

    Stores collection manifests as JSON files in a hidden .artcollector
    directory within the output folder.
    """

    def __init__(self, output_folder: str | Path):
        """
        Initialize manifest storage backend.

        Args:
            output_folder: The output folder for this collection
        """
        self.output_folder = Path(output_folder)
        self.manifest_dir = self.output_folder / MANIFEST_DIR
        self.manifest_path = self.manifest_dir / MANIFEST_FILE
        self._lock = asyncio.Lock()
        self._cache: CollectionManifest | None = None

    async def _ensure_dir(self) -> None:
        """Ensure manifest directory exists."""
        self.manifest_dir.mkdir(parents=True, exist_ok=True)

    async def _load_or_create_locked(self) -> CollectionManifest:
        """
        Load existing manifest or create a new one.

        IMPORTANT: Caller must hold self._lock before calling this method.
        """
        if self._cache is not None:
            return self._cache

        if self.manifest_path.exists():
            try:
                data = await asyncio.to_thread(self.manifest_path.read_text, encoding="utf-8")
                manifest_dict = json.loads(data)
                self._cache = CollectionManifest.model_validate(manifest_dict)
                return self._cache
            except (json.JSONDecodeError, ValueError, ValidationError) as e:
                logger.warning(f"Failed to load manifest, creating new: {e}")

        # Create new manifest
        now = datetime.now(UTC).isoformat()
        self._cache = CollectionManifest(
            manifest_id=self.output_folder.name,
            created_at=now,
            updated_at=now,
            source_type="local",
            output_folder=str(self.output_folder),
        )
        return self._cache

    async def _save(self, manifest: CollectionManifest) -> None:
        """Save manifest to disk."""
        await self._ensure_dir()
        manifest.updated_at = datetime.now(UTC).isoformat()
        data = manifest.model_dump_json(indent=2)
        await asyncio.to_thread(self.manifest_path.write_text, data, encoding="utf-8")
        self._cache = manifest

    async def save_artifact(self, artifact: ArtifactManifestEntry) -> None:
        """Save artifact metadata to manifest."""
        async with self._lock:
            manifest = await self._load_or_create_locked()

            # Check for existing artifact with same ID (update case)
            existing_idx = next(
                (
                    i
                    for i, a in enumerate(manifest.artifacts)
                    if a.artifact_id == artifact.artifact_id
                ),
                None,
            )
            if existing_idx is not None:
                manifest.artifacts[existing_idx] = artifact
            else:
                manifest.artifacts.append(artifact)

            await self._save(manifest)

    async def find_by_id(self, artifact_id: str) -> ArtifactManifestEntry | None:
        """Find artifact by persistent ID."""
        async with self._lock:
            manifest = await self._load_or_create_locked()
            return next((a for a in manifest.artifacts if a.artifact_id == artifact_id), None)

    async def find_by_hash(self, content_hash: str) -> list[ArtifactManifestEntry]:
        """Find artifacts by content hash."""
        async with self._lock:
            manifest = await self._load_or_create_locked()
            return [a for a in manifest.artifacts if a.content_hash == content_hash]

    async def update_location(self, artifact_id: str, new_path: str) -> bool:
        """
        Update artifact location after file move.

        Args:
            artifact_id: The artifact's persistent ID
            new_path: New file path (must be within output_folder)

        Returns:
            True if updated, False if artifact not found

        Raises:
            ValueError: If new_path is outside the output folder
        """

        # Validate that new_path is within the output folder
        # Offload blocking Path.resolve() calls to thread pool
        def _validate_path() -> None:
            resolved_new = Path(new_path).resolve()
            resolved_output = self.output_folder.resolve()
            resolved_new.relative_to(resolved_output)

        try:
            await asyncio.to_thread(_validate_path)
        except ValueError as e:
            raise ValueError(
                f"new_path must be within output folder. "
                f"Got '{new_path}', expected path under '{self.output_folder}'"
            ) from e

        async with self._lock:
            manifest = await self._load_or_create_locked()

            for artifact in manifest.artifacts:
                if artifact.artifact_id == artifact_id:
                    artifact.current_filename = new_path
                    await self._save(manifest)
                    return True

            return False

    async def save_collection(self, manifest: CollectionManifest) -> None:
        """Save full collection manifest."""
        async with self._lock:
            await self._save(manifest)

    async def load_collection(self, manifest_id: str) -> CollectionManifest | None:
        """Load collection manifest by ID."""
        async with self._lock:
            manifest = await self._load_or_create_locked()
            if manifest.manifest_id == manifest_id:
                return manifest
            return None

    async def list_collections(self) -> list[str]:
        """List all collection manifest IDs in this output folder."""
        async with self._lock:
            if self.manifest_path.exists():
                manifest = await self._load_or_create_locked()
                return [manifest.manifest_id]
            return []

    def invalidate_cache(self) -> None:
        """Invalidate the in-memory cache (forces reload on next access)."""
        self._cache = None
