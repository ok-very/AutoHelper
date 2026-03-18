"""
Collectors submodule.

Provides artifact collectors for different source types (web, folder).
"""

from .base import (
    MAX_IMAGES,
    REQUEST_TIMEOUT,
    SUPPORTED_DOCUMENT_EXTENSIONS,
    SUPPORTED_IMAGE_EXTENSIONS,
    CollectorProtocol,
    get_artifact_type,
    scan_files_safe,
)
from .folder import FolderCollector
from .web import WebCollector

__all__ = [
    "CollectorProtocol",
    "WebCollector",
    "FolderCollector",
    "scan_files_safe",
    "get_artifact_type",
    "SUPPORTED_IMAGE_EXTENSIONS",
    "SUPPORTED_DOCUMENT_EXTENSIONS",
    "MAX_IMAGES",
    "REQUEST_TIMEOUT",
]
