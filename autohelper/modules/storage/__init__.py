"""
Storage module - Pluggable backends for artifact metadata persistence.

Supports:
- JSON manifest (default, local file-based)
- SharePoint (optional, requires credentials)
"""

from .base import MetadataStorageBackend
from .manifest_backend import ManifestStorageBackend
from .router import get_metadata_backend

__all__ = [
    "MetadataStorageBackend",
    "ManifestStorageBackend",
    "get_metadata_backend",
]
