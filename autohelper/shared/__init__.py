"""Shared types, errors, and utilities."""

from .errors import (
    AutoHelperError,
    ConflictError,
    NotFoundError,
    OutOfBoundsPathError,
    UnsafeSymlinkError,
    ValidationError,
)
from .types import FileInfo, IndexRunStatus, OperationResult, RequestContext, RootInfo

__all__ = [
    "AutoHelperError",
    "ConflictError",
    "NotFoundError",
    "OutOfBoundsPathError",
    "UnsafeSymlinkError",
    "ValidationError",
    "FileInfo",
    "IndexRunStatus",
    "OperationResult",
    "RequestContext",
    "RootInfo",
]
