"""
SharePoint storage backend (optional).

Stores artifact metadata in a SharePoint list for enterprise environments.
Requires the Office365-REST-Python-Client package:
    pip install Office365-REST-Python-Client

Or install the optional dependency:
    pip install autohelper[sharepoint]
"""

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from ..runner.types import (
    ArtifactManifestEntry,
    CollectionManifest,
    NamingConfig,
)

logger = logging.getLogger(__name__)

# SharePoint list names
COLLECTIONS_LIST = "ArtifactCollections"
ARTIFACTS_LIST = "CollectedArtifacts"


def _escape_odata_string(value: str) -> str:
    """Escape a string for safe use in OData filter expressions."""
    # OData string literals use single quotes; escape embedded single quotes by doubling them
    return value.replace("'", "''")


def _lazy_import_office365() -> tuple[type, type]:
    """Lazily import office365 to avoid import errors when not installed."""
    try:
        from office365.runtime.auth.client_credential import ClientCredential
        from office365.sharepoint.client_context import ClientContext

        return ClientCredential, ClientContext
    except ImportError as e:
        raise ImportError(
            "SharePoint backend requires 'Office365-REST-Python-Client' package. "
            "Install with: pip install Office365-REST-Python-Client "
            "or: pip install autohelper[sharepoint]"
        ) from e


class SharePointStorageBackend:
    """
    SharePoint-based metadata storage backend.

    Stores artifact metadata in SharePoint lists for enterprise environments
    where centralized tracking is required.

    Lists used:
    - ArtifactCollections: Collection manifests (one item per collection)
    - CollectedArtifacts: Individual artifact entries (many items per collection)

    Required SharePoint permissions:
    - Sites.ReadWrite.All (or specific site permissions)
    - Lists.ReadWrite.All
    """

    def __init__(
        self,
        site_url: str,
        client_id: str,
        client_secret: str,
        output_folder: str | Path,
    ):
        """
        Initialize SharePoint storage backend.

        Args:
            site_url: SharePoint site URL (e.g., https://contoso.sharepoint.com/sites/art)
            client_id: Azure AD app client ID
            client_secret: Azure AD app client secret
            output_folder: Local output folder (used for manifest_id generation)
        """
        self.site_url = site_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.output_folder = Path(output_folder)

        # Lock only for _ensure_lists coordination
        self._lists_lock = asyncio.Lock()
        self._lists_ensured = False

    def _create_context(self) -> Any:
        """Create a new SharePoint client context (thread-safe, one per operation)."""
        ClientCredential, ClientContext = _lazy_import_office365()
        credentials = ClientCredential(self.client_id, self.client_secret)
        return ClientContext(self.site_url).with_credentials(credentials)

    async def _ensure_lists(self) -> None:
        """Ensure required SharePoint lists exist (cached after first check)."""
        # Double-check pattern: quick check, then lock, then re-check
        if self._lists_ensured:
            return

        async with self._lists_lock:
            if self._lists_ensured:
                return

            def _create_lists() -> None:
                ctx = self._create_context()
                web = ctx.web
                ctx.load(web.lists)
                ctx.execute_query()

                list_titles = {lst.properties.get("Title", "") for lst in web.lists}

                # Create collections list if missing
                if COLLECTIONS_LIST not in list_titles:
                    logger.info(f"Creating SharePoint list: {COLLECTIONS_LIST}")
                    list_creation_info = {
                        "Title": COLLECTIONS_LIST,
                        "Description": "Artifact collection manifests",
                        "BaseTemplate": 100,  # Generic list
                    }
                    web.lists.add(list_creation_info)
                    ctx.execute_query()

                # Create artifacts list if missing
                if ARTIFACTS_LIST not in list_titles:
                    logger.info(f"Creating SharePoint list: {ARTIFACTS_LIST}")
                    list_creation_info = {
                        "Title": ARTIFACTS_LIST,
                        "Description": "Collected artifact metadata",
                        "BaseTemplate": 100,
                    }
                    web.lists.add(list_creation_info)
                    ctx.execute_query()

            await asyncio.to_thread(_create_lists)
            self._lists_ensured = True

    def _artifact_to_list_item(
        self, artifact: ArtifactManifestEntry, collection_id: str | None = None
    ) -> dict[str, Any]:
        """Convert artifact entry to SharePoint list item fields."""
        return {
            "Title": artifact.artifact_id,
            "CollectionId": collection_id or "",
            "OriginalFilename": artifact.original_filename,
            "CurrentFilename": artifact.current_filename,
            "ContentHash": artifact.content_hash,
            "SourceUrl": artifact.source_url or "",
            "SourcePath": artifact.source_path or "",
            "CollectedAt": artifact.collected_at,
            "MimeType": artifact.mime_type,
            "FileSize": artifact.size,
            "MetadataJson": json.dumps(artifact.metadata) if artifact.metadata else "{}",
        }

    def _list_item_to_artifact(self, item: dict[str, Any]) -> ArtifactManifestEntry:
        """Convert SharePoint list item to artifact entry."""
        metadata: dict[str, Any] = {}
        metadata_json = item.get("MetadataJson", "{}")
        if metadata_json:
            try:
                # If already a dict, use as-is; otherwise attempt JSON deserialization
                if isinstance(metadata_json, dict):
                    metadata = metadata_json
                else:
                    metadata = json.loads(metadata_json)
            except (json.JSONDecodeError, TypeError):
                logger.warning(
                    f"Malformed MetadataJson for artifact {item.get('Title')}"
                )
                metadata = {}

        # Safely parse FileSize, defaulting to 0 if malformed
        file_size = 0
        try:
            file_size = int(item.get("FileSize", 0))
        except (ValueError, TypeError):
            logger.warning(f"Malformed FileSize for artifact {item.get('Title')}")

        collected_at_value = item.get("CollectedAt") or None
        collected_at_str = str(collected_at_value) if collected_at_value is not None else ""

        return ArtifactManifestEntry(
            artifact_id=item.get("Title", ""),
            original_filename=item.get("OriginalFilename", ""),
            current_filename=item.get("CurrentFilename", ""),
            content_hash=item.get("ContentHash", ""),
            source_url=item.get("SourceUrl") or None,
            source_path=item.get("SourcePath") or None,
            collected_at=collected_at_str,
            mime_type=item.get("MimeType", "application/octet-stream"),
            size=file_size,
            metadata=metadata,
        )


    async def save_artifact(
        self, artifact: ArtifactManifestEntry, collection_id: str | None = None
    ) -> None:
        """Save artifact metadata to SharePoint list."""
        await self._ensure_lists()

        def _save() -> None:
            ctx = self._create_context()
            artifacts_list = ctx.web.lists.get_by_title(ARTIFACTS_LIST)

            # Check if artifact already exists using CAML query
            items = artifacts_list.get_items().filter(
                f"Title eq '{_escape_odata_string(artifact.artifact_id)}'"
            )
            ctx.load(items)
            ctx.execute_query()

            item_data = self._artifact_to_list_item(artifact, collection_id)

            if len(items) > 0:
                # Update existing item
                existing_item = items[0]
                for key, value in item_data.items():
                    if key != "Title":  # Don't update Title (primary key)
                        existing_item.set_property(key, value)
                existing_item.update()
                ctx.execute_query()
                logger.debug(f"Updated artifact in SharePoint: {artifact.artifact_id}")
            else:
                # Create new item
                artifacts_list.add_item(item_data)
                ctx.execute_query()
                logger.debug(f"Created artifact in SharePoint: {artifact.artifact_id}")

        await asyncio.to_thread(_save)

    async def find_by_id(self, artifact_id: str) -> ArtifactManifestEntry | None:
        """Find artifact by persistent ID."""
        await self._ensure_lists()

        def _find() -> dict[str, Any] | None:
            ctx = self._create_context()
            artifacts_list = ctx.web.lists.get_by_title(ARTIFACTS_LIST)
            items = artifacts_list.get_items().filter(
                f"Title eq '{_escape_odata_string(artifact_id)}'"
            )
            ctx.load(items)
            ctx.execute_query()

            if len(items) > 0:
                return cast(dict[str, Any], items[0].properties)
            return None

        result = await asyncio.to_thread(_find)

        if result:
            return self._list_item_to_artifact(result)
        return None

    async def find_by_hash(self, content_hash: str) -> list[ArtifactManifestEntry]:
        """Find artifacts by content hash."""
        await self._ensure_lists()

        def _find() -> list[dict[str, Any]]:
            ctx = self._create_context()
            artifacts_list = ctx.web.lists.get_by_title(ARTIFACTS_LIST)
            items = artifacts_list.get_items().filter(
                f"ContentHash eq '{_escape_odata_string(content_hash)}'"
            )
            ctx.load(items)
            ctx.execute_query()
            return [item.properties for item in items]

        results = await asyncio.to_thread(_find)
        return [self._list_item_to_artifact(r) for r in results]

    async def update_location(self, artifact_id: str, new_path: str) -> bool:
        """Update artifact location after file move."""
        await self._ensure_lists()

        def _update() -> bool:
            ctx = self._create_context()
            artifacts_list = ctx.web.lists.get_by_title(ARTIFACTS_LIST)
            items = artifacts_list.get_items().filter(
                f"Title eq '{_escape_odata_string(artifact_id)}'"
            )
            ctx.load(items)
            ctx.execute_query()

            if len(items) > 0:
                items[0].set_property("CurrentFilename", new_path)
                items[0].update()
                ctx.execute_query()
                logger.debug(f"Updated location for {artifact_id}: {new_path}")
                return True
            return False

        return await asyncio.to_thread(_update)

    async def save_collection(self, manifest: CollectionManifest) -> None:
        """Save full collection manifest to SharePoint."""
        await self._ensure_lists()

        # First save all artifacts, track failures
        failed_artifacts: list[str] = []
        for artifact in manifest.artifacts:
            try:
                await self.save_artifact(artifact, collection_id=manifest.manifest_id)
            except Exception as e:
                logger.error(f"Failed to save artifact {artifact.artifact_id}: {e}")
                failed_artifacts.append(artifact.artifact_id)

        # Calculate actual saved count
        saved_count = len(manifest.artifacts) - len(failed_artifacts)

        def _save_manifest() -> None:
            ctx = self._create_context()
            collections_list = ctx.web.lists.get_by_title(COLLECTIONS_LIST)

            # Check if collection exists
            items = collections_list.get_items().filter(
                f"Title eq '{_escape_odata_string(manifest.manifest_id)}'"
            )
            ctx.load(items)
            ctx.execute_query()

            # Parse ISO strings to datetime for SharePoint DateTime field compatibility
            try:
                created_at_dt = datetime.fromisoformat(manifest.created_at.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                # Fallback to current time if parsing fails
                created_at_dt = datetime.now(UTC)
            updated_at_dt = datetime.now(UTC)

            item_data = {
                "Title": manifest.manifest_id,
                "Version": manifest.version,
                "CreatedAt": created_at_dt,
                "UpdatedAt": updated_at_dt,
                "SourceType": manifest.source_type,
                "SourceUrl": manifest.source_url or "",
                "SourcePath": manifest.source_path or "",
                "OutputFolder": manifest.output_folder,
                "NamingTemplate": manifest.naming_config.template,
                "IndexStart": manifest.naming_config.index_start,
                "IndexPadding": manifest.naming_config.index_padding,
                "ArtifactCount": saved_count,  # Reflect actual saved count
            }

            if len(items) > 0:
                # Update existing
                existing_item = items[0]
                for key, value in item_data.items():
                    if key != "Title":
                        existing_item.set_property(key, value)
                existing_item.update()
                ctx.execute_query()
                logger.info(f"Updated collection in SharePoint: {manifest.manifest_id}")
            else:
                # Create new
                collections_list.add_item(item_data)
                ctx.execute_query()
                logger.info(f"Created collection in SharePoint: {manifest.manifest_id}")

        # Only save manifest if at least one artifact was saved successfully
        if saved_count > 0:
            await asyncio.to_thread(_save_manifest)
            # Log partial failures as warning, but don't raise (partial success)
            if failed_artifacts:
                sample = failed_artifacts[:5]
                suffix = "..." if len(failed_artifacts) > 5 else ""
                logger.warning(
                    f"Collection {manifest.manifest_id} saved with {len(failed_artifacts)} "
                    f"failed artifacts: {sample}{suffix}"
                )
        else:
            # All artifacts failed - raise error
            raise RuntimeError(
                f"Collection {manifest.manifest_id}: All {len(manifest.artifacts)} "
                "artifacts failed to save"
            )

    async def load_collection(self, manifest_id: str) -> CollectionManifest | None:
        """Load collection manifest from SharePoint."""
        await self._ensure_lists()

        def _load() -> dict[str, Any] | None:
            ctx = self._create_context()
            collections_list = ctx.web.lists.get_by_title(COLLECTIONS_LIST)
            items = collections_list.get_items().filter(
                f"Title eq '{_escape_odata_string(manifest_id)}'"
            )
            ctx.load(items)
            ctx.execute_query()

            if len(items) > 0:
                return cast(dict[str, Any], items[0].properties)
            return None

        collection_data = await asyncio.to_thread(_load)

        if not collection_data:
            return None

        # Load artifacts for this collection
        def _load_artifacts() -> list[dict[str, Any]]:
            ctx = self._create_context()
            artifacts_list = ctx.web.lists.get_by_title(ARTIFACTS_LIST)
            items = artifacts_list.get_items().filter(
                f"CollectionId eq '{_escape_odata_string(manifest_id)}'"
            )
            ctx.load(items)
            ctx.execute_query()
            return [item.properties for item in items]

        artifact_data = await asyncio.to_thread(_load_artifacts)
        artifacts = [self._list_item_to_artifact(a) for a in artifact_data]

        # Safely parse index fields with defaults for malformed values
        index_start = 1
        index_padding = 3
        try:
            index_start = int(collection_data.get("IndexStart", 1))
        except (ValueError, TypeError):
            logger.warning(f"Malformed IndexStart for collection {manifest_id}, using default")
        try:
            index_padding = int(collection_data.get("IndexPadding", 3))
        except (ValueError, TypeError):
            logger.warning(f"Malformed IndexPadding for collection {manifest_id}, using default")

        # Reconstruct naming config from stored fields
        naming_config = NamingConfig(
            template=collection_data.get("NamingTemplate", "{index}_{hash}"),
            index_start=index_start,
            index_padding=index_padding,
        )

        # Handle datetime values from SharePoint - convert to ISO strings if needed
        def _to_iso_string(val: Any) -> str:
            if val is None:
                return ""
            if isinstance(val, datetime):
                return val.isoformat()
            return str(val)

        return CollectionManifest(
            manifest_id=collection_data.get("Title", ""),
            version=collection_data.get("Version", "1.0"),
            created_at=_to_iso_string(collection_data.get("CreatedAt")),
            updated_at=_to_iso_string(collection_data.get("UpdatedAt")),
            source_type=collection_data.get("SourceType", "local"),
            source_url=collection_data.get("SourceUrl") or None,
            source_path=collection_data.get("SourcePath") or None,
            output_folder=collection_data.get("OutputFolder", ""),
            naming_config=naming_config,
            artifacts=artifacts,
        )

    async def list_collections(self) -> list[str]:
        """List all collection manifest IDs from SharePoint."""
        await self._ensure_lists()

        def _list() -> list[str]:
            ctx = self._create_context()
            collections_list = ctx.web.lists.get_by_title(COLLECTIONS_LIST)
            items = collections_list.get_items().select(["Title"])
            ctx.load(items)
            ctx.execute_query()
            return [
                item.properties.get("Title", "")
                for item in items
                if item.properties.get("Title")
            ]

        return await asyncio.to_thread(_list)
