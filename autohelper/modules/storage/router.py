"""
Storage router - Factory for selecting metadata storage backend.

Selects the appropriate backend based on configuration settings.
"""

import logging
from pathlib import Path

from ...config.settings import Settings, get_settings
from .base import MetadataStorageBackend
from .manifest_backend import ManifestStorageBackend

logger = logging.getLogger(__name__)


def get_metadata_backend(
    output_folder: str | Path,
    settings: Settings | None = None,
) -> MetadataStorageBackend:
    """
    Factory function to get the configured metadata storage backend.

    Args:
        output_folder: The output folder for artifact storage
        settings: Optional settings override (uses global settings if None)

    Returns:
        Configured MetadataStorageBackend instance

    Raises:
        ValueError: If the configured backend is invalid or missing required config
    """
    if settings is None:
        settings = get_settings()

    backend_type = settings.metadata_backend

    match backend_type:
        case "manifest":
            logger.debug(f"Using manifest backend for {output_folder}")
            return ManifestStorageBackend(output_folder)

        case "sharepoint":
            # Validate SharePoint configuration
            if not all(
                [
                    settings.sharepoint_site_url,
                    settings.sharepoint_client_id,
                    settings.sharepoint_client_secret,
                ]
            ):
                raise ValueError(
                    "SharePoint backend requires AUTOHELPER_SHAREPOINT_SITE_URL, "
                    "AUTOHELPER_SHAREPOINT_CLIENT_ID, and AUTOHELPER_SHAREPOINT_CLIENT_SECRET"
                )

            # Import SharePoint backend lazily to avoid dependency if not used
            try:
                from .sharepoint_backend import SharePointStorageBackend
            except ImportError as e:
                raise ValueError(
                    "SharePoint backend requires 'office365-rest-python-client' package. "
                    "Install with: pip install office365-rest-python-client"
                ) from e

            logger.debug(f"Using SharePoint backend for {output_folder}")
            # Type narrowing: we've validated these are not None above
            assert settings.sharepoint_site_url is not None
            assert settings.sharepoint_client_id is not None
            assert settings.sharepoint_client_secret is not None
            return SharePointStorageBackend(
                site_url=settings.sharepoint_site_url,
                client_id=settings.sharepoint_client_id,
                client_secret=settings.sharepoint_client_secret,
                output_folder=output_folder,
            )

        case _:
            raise ValueError(f"Unknown metadata backend: {backend_type}")
