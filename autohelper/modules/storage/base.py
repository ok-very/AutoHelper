"""
Base protocol for metadata storage backends.

All backends must implement this interface to be used with the storage router.
"""

from typing import Protocol, runtime_checkable

from ..runner.types import ArtifactManifestEntry, CollectionManifest


@runtime_checkable
class MetadataStorageBackend(Protocol):
    """
    Protocol for artifact metadata storage backends.

    Implementations must provide methods for:
    - Saving individual artifacts
    - Finding artifacts by ID or content hash
    - Updating artifact locations (for moved files)
    - Saving/loading full collection manifests
    """

    async def save_artifact(self, artifact: ArtifactManifestEntry) -> None:
        """
        Save artifact metadata to storage.

        Args:
            artifact: The artifact entry to save
        """
        ...

    async def find_by_id(self, artifact_id: str) -> ArtifactManifestEntry | None:
        """
        Find artifact by its persistent ID.

        Args:
            artifact_id: The stable UUID of the artifact

        Returns:
            The artifact entry if found, None otherwise
        """
        ...

    async def find_by_hash(self, content_hash: str) -> list[ArtifactManifestEntry]:
        """
        Find artifacts by content hash (for relocated files).

        Args:
            content_hash: SHA-256 hash of file content

        Returns:
            List of matching artifact entries (may be empty)
        """
        ...

    async def update_location(self, artifact_id: str, new_path: str) -> bool:
        """
        Update artifact location after file move detection.

        Args:
            artifact_id: The stable UUID of the artifact
            new_path: The new file path

        Returns:
            True if update succeeded, False if artifact not found
        """
        ...

    async def save_collection(self, manifest: CollectionManifest) -> None:
        """
        Save full collection manifest.

        Args:
            manifest: The complete collection manifest to save
        """
        ...

    async def load_collection(self, manifest_id: str) -> CollectionManifest | None:
        """
        Load collection manifest by ID.

        Args:
            manifest_id: The unique collection ID

        Returns:
            The collection manifest if found, None otherwise
        """
        ...

    async def list_collections(self) -> list[str]:
        """
        List all available collection manifest IDs.

        Returns:
            List of manifest IDs
        """
        ...
