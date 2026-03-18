"""
Artifact Lookup Service

Provides artifact lookup across storage backends (manifest JSON or SharePoint).
Can find artifacts by ID or content hash, even if files have been moved.
"""

import asyncio
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from autohelper.config.settings import Settings, get_settings
from autohelper.db.conn import get_db

from ..storage.router import get_metadata_backend
from .types import ArtifactManifestEntry, CollectionManifest

logger = logging.getLogger(__name__)


class ArtifactLookupService:
    """
    Service for looking up artifacts across all storage backends.

    Provides methods to:
    - Find artifacts by persistent ID
    - Find artifacts by content hash (for relocated files)
    - List all collections
    - Sync manifest data to database for faster queries
    """

    def __init__(self, settings: Settings | None = None):
        """
        Initialize lookup service.

        Args:
            settings: Optional settings override (uses global if None)
        """
        self._settings = settings or get_settings()

    async def find_artifact_by_id(
        self,
        artifact_id: str,
        output_folder: str | Path | None = None,
    ) -> ArtifactManifestEntry | None:
        """
        Find artifact by its persistent ID.

        If output_folder is provided, searches only that folder's manifest.
        Otherwise, searches the database for all known collections.

        Args:
            artifact_id: The stable UUID of the artifact
            output_folder: Optional - specific folder to search

        Returns:
            The artifact entry if found, None otherwise
        """
        # If specific folder provided, use its backend directly
        if output_folder is not None:
            backend = get_metadata_backend(output_folder, self._settings)
            return await backend.find_by_id(artifact_id)

        # Otherwise, search database for collection containing this artifact
        try:
            def _query_db() -> Any:
                db = get_db()
                return db.execute(
                    """
                    SELECT ca.*, ac.output_folder
                    FROM collected_artifacts ca
                    JOIN artifact_collections ac ON ca.collection_id = ac.collection_id
                    WHERE ca.artifact_id = ?
                    """,
                    (artifact_id,),
                ).fetchone()

            row = await asyncio.to_thread(_query_db)

            if row:
                return self._row_to_artifact_entry(dict(row))

            # Fallback: search allowed roots for manifest files
            return await self._search_manifests_by_id(artifact_id)

        except RuntimeError:
            # Database not initialized, search manifests directly
            return await self._search_manifests_by_id(artifact_id)

    async def find_artifacts_by_hash(
        self,
        content_hash: str,
        output_folder: str | Path | None = None,
    ) -> list[ArtifactManifestEntry]:
        """
        Find artifacts by content hash (for relocated files).

        Args:
            content_hash: SHA-256 hash of file content
            output_folder: Optional - specific folder to search

        Returns:
            List of matching artifact entries
        """
        # If specific folder provided, use its backend directly
        if output_folder is not None:
            backend = get_metadata_backend(output_folder, self._settings)
            return await backend.find_by_hash(content_hash)

        # Search database
        try:
            def _query_db() -> list[Any]:
                db = get_db()
                return db.execute(
                    """
                    SELECT ca.*, ac.output_folder
                    FROM collected_artifacts ca
                    JOIN artifact_collections ac ON ca.collection_id = ac.collection_id
                    WHERE ca.content_hash = ?
                    """,
                    (content_hash,),
                ).fetchall()

            rows = await asyncio.to_thread(_query_db)

            if rows:
                return [self._row_to_artifact_entry(dict(row)) for row in rows]

            # Fallback: search manifests
            return await self._search_manifests_by_hash(content_hash)

        except RuntimeError:
            return await self._search_manifests_by_hash(content_hash)

    async def list_collections(
        self,
        output_folder: str | Path | None = None,
    ) -> list[dict[str, Any]]:
        """
        List all artifact collections.

        Args:
            output_folder: Optional - filter to specific folder

        Returns:
            List of collection summaries with id, source, artifact_count
        """
        try:
            def _query_db() -> list[Any]:
                db = get_db()
                if output_folder:
                    return db.execute(
                        """
                        SELECT collection_id, source_type, source_url, source_path,
                               output_folder, artifact_count, created_at, status
                        FROM artifact_collections
                        WHERE output_folder = ? AND status = 'active'
                        ORDER BY created_at DESC
                        """,
                        (str(output_folder),),
                    ).fetchall()
                else:
                    return db.execute(
                        """
                        SELECT collection_id, source_type, source_url, source_path,
                               output_folder, artifact_count, created_at, status
                        FROM artifact_collections
                        WHERE status = 'active'
                        ORDER BY created_at DESC
                        """,
                    ).fetchall()

            rows = await asyncio.to_thread(_query_db)
            return [dict(row) for row in rows]

        except RuntimeError:
            # Database not initialized
            return []

    async def get_collection(
        self,
        collection_id: str,
    ) -> CollectionManifest | None:
        """
        Get full collection manifest by ID.

        Args:
            collection_id: The collection's unique ID

        Returns:
            The collection manifest if found, None otherwise
        """
        try:
            def _query_db() -> Any:
                db = get_db()
                return db.execute(
                    "SELECT output_folder FROM artifact_collections WHERE collection_id = ?",
                    (collection_id,),
                ).fetchone()

            row = await asyncio.to_thread(_query_db)

            if row:
                output_folder = row["output_folder"]
                backend = get_metadata_backend(output_folder, self._settings)
                return await backend.load_collection(collection_id)

            return None

        except RuntimeError:
            return None

    async def sync_collection_to_db(
        self,
        manifest: CollectionManifest,
    ) -> None:
        """
        Sync a collection manifest to the database for faster lookups.

        Args:
            manifest: The collection manifest to sync
        """
        try:
            def _sync_db() -> None:
                db = get_db()

                # Upsert collection
                db.execute(
                    """
                    INSERT INTO artifact_collections (
                        collection_id, manifest_path, source_type, source_url,
                        source_path, output_folder, naming_template, created_at,
                        updated_at, artifact_count, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
                    ON CONFLICT(collection_id) DO UPDATE SET
                        updated_at = excluded.updated_at,
                        artifact_count = excluded.artifact_count
                    """,
                    (
                        manifest.manifest_id,
                        f"{manifest.output_folder}/.artcollector/manifest.json",
                        manifest.source_type,
                        manifest.source_url,
                        manifest.source_path,
                        manifest.output_folder,
                        manifest.naming_config.template,
                        manifest.created_at,
                        manifest.updated_at,
                        len(manifest.artifacts),
                    ),
                )

                # Upsert artifacts
                for artifact in manifest.artifacts:
                    db.execute(
                        """
                        INSERT INTO collected_artifacts (
                            artifact_id, collection_id, content_hash, original_filename,
                            current_filename, source_url, source_path, collected_at,
                            mime_type, size, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(artifact_id) DO UPDATE SET
                            current_filename = excluded.current_filename,
                            metadata_json = excluded.metadata_json
                        """,
                        (
                            artifact.artifact_id,
                            manifest.manifest_id,
                            artifact.content_hash,
                            artifact.original_filename,
                            artifact.current_filename,
                            artifact.source_url,
                            artifact.source_path,
                            artifact.collected_at,
                            artifact.mime_type,
                            artifact.size,
                            json.dumps(artifact.metadata),
                        ),
                    )

                db.commit()

            await asyncio.to_thread(_sync_db)
            logger.info(
                f"Synced collection {manifest.manifest_id} "
                f"with {len(manifest.artifacts)} artifacts to database"
            )

        except RuntimeError as e:
            logger.warning(f"Could not sync to database: {e}")

    async def update_artifact_location(
        self,
        artifact_id: str,
        new_path: str,
        output_folder: str | Path,
    ) -> bool:
        """
        Update artifact location after file move.

        Updates both the manifest and database.

        Args:
            artifact_id: The artifact's persistent ID
            new_path: The new file path
            output_folder: The collection's output folder

        Returns:
            True if update succeeded, False otherwise
        """
        # Update in manifest backend
        backend = get_metadata_backend(output_folder, self._settings)
        success = await backend.update_location(artifact_id, new_path)

        if not success:
            return False

        # Also update in database, scoped to the collection's output_folder
        db_updated = False
        try:
            def _update_db() -> bool:
                db = get_db()
                # Get collection_id for this output_folder to scope the update
                collection_row = db.execute(
                    "SELECT collection_id FROM artifact_collections WHERE output_folder = ?",
                    (str(output_folder),),
                ).fetchone()

                if collection_row:
                    db.execute(
                        """
                        UPDATE collected_artifacts
                        SET current_filename = ?
                        WHERE artifact_id = ? AND collection_id = ?
                        """,
                        (new_path, artifact_id, collection_row["collection_id"]),
                    )
                    db.commit()
                    return True
                else:
                    # No collection found for folder - this is a data integrity issue
                    logger.warning(
                        f"No collection found for output_folder {output_folder}, "
                        f"database not updated for artifact {artifact_id}"
                    )
                    return False

            db_updated = await asyncio.to_thread(_update_db)
        except RuntimeError:
            # Database not available - manifest was updated but DB sync failed
            logger.warning("Database not available, only manifest was updated")
            db_updated = False

        # Return True only if both manifest and database were updated
        return db_updated

    async def compute_file_hash(self, file_path: str | Path) -> str:
        """
        Compute SHA-256 hash of a file.

        Args:
            file_path: Path to the file

        Returns:
            Hex-encoded SHA-256 hash

        Raises:
            FileNotFoundError: If file does not exist
            PermissionError: If file cannot be read
            OSError: For other filesystem errors
        """
        def _hash_file() -> str:
            try:
                sha256 = hashlib.sha256()
                with open(file_path, "rb") as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        sha256.update(chunk)
                return sha256.hexdigest()
            except FileNotFoundError:
                logger.error(f"File not found for hashing: {file_path}")
                raise
            except PermissionError:
                logger.error(f"Permission denied reading file: {file_path}")
                raise
            except OSError as e:
                logger.error(f"OS error hashing file {file_path}: {e}")
                raise

        return await asyncio.to_thread(_hash_file)

    async def _search_manifests_by_id(
        self,
        artifact_id: str,
    ) -> ArtifactManifestEntry | None:
        """Search manifest files in allowed roots for artifact by ID."""
        for root in self._settings.get_allowed_roots():
            for manifest_path in root.rglob(".artcollector/manifest.json"):
                try:
                    output_folder = manifest_path.parent.parent
                    backend = get_metadata_backend(output_folder, self._settings)
                    artifact = await backend.find_by_id(artifact_id)
                    if artifact:
                        return artifact
                except Exception as e:
                    logger.debug(f"Error searching manifest {manifest_path}: {e}")
                    continue
        return None

    async def _search_manifests_by_hash(
        self,
        content_hash: str,
    ) -> list[ArtifactManifestEntry]:
        """Search manifest files in allowed roots for artifacts by hash."""
        results: list[ArtifactManifestEntry] = []
        for root in self._settings.get_allowed_roots():
            for manifest_path in root.rglob(".artcollector/manifest.json"):
                try:
                    output_folder = manifest_path.parent.parent
                    backend = get_metadata_backend(output_folder, self._settings)
                    artifacts = await backend.find_by_hash(content_hash)
                    results.extend(artifacts)
                except Exception as e:
                    logger.debug(f"Error searching manifest {manifest_path}: {e}")
                    continue
        return results

    def _row_to_artifact_entry(self, row: dict[str, Any]) -> ArtifactManifestEntry:
        """Convert database row to ArtifactManifestEntry."""
        metadata = {}
        if row.get("metadata_json"):
            try:
                metadata = json.loads(row["metadata_json"])
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(
                    f"Malformed metadata_json for artifact {row.get('artifact_id')}: {e}"
                )

        return ArtifactManifestEntry(
            artifact_id=row["artifact_id"],
            original_filename=row["original_filename"],
            current_filename=row["current_filename"],
            content_hash=row["content_hash"],
            source_url=row.get("source_url"),
            source_path=row.get("source_path"),
            collected_at=row["collected_at"],
            mime_type=row.get("mime_type", "application/octet-stream"),
            size=row.get("size", 0),
            metadata=metadata,
        )


# Global service instance
_lookup_service: ArtifactLookupService | None = None


def get_lookup_service() -> ArtifactLookupService:
    """Get or create the global lookup service."""
    global _lookup_service
    if _lookup_service is None:
        _lookup_service = ArtifactLookupService()
    return _lookup_service
