"""
Typed error hierarchy with stable machine-readable codes.
All errors have consistent structure for AutoArt integration.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AutoHelperError(Exception):
    """Base error with stable error code for API responses."""
    
    code: str
    message: str
    http_status: int = 500
    details: dict[str, Any] = field(default_factory=dict)
    
    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to API response format."""
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class OutOfBoundsPathError(AutoHelperError):
    """Path is outside allowed roots."""
    
    code: str = "PATH_OUT_OF_ROOT"
    message: str = "Path is outside allowed root directories"
    http_status: int = 403
    path: str = ""
    
    def __post_init__(self) -> None:
        if self.path:
            self.details["path"] = self.path


@dataclass
class UnsafeSymlinkError(AutoHelperError):
    """Symlink traversal blocked by policy."""
    
    code: str = "PATH_SYMLINK_BLOCKED"
    message: str = "Symlink traversal is blocked by security policy"
    http_status: int = 403
    path: str = ""
    
    def __post_init__(self) -> None:
        if self.path:
            self.details["path"] = self.path


@dataclass
class NotFoundError(AutoHelperError):
    """Resource not found."""
    
    code: str = "NOT_FOUND"
    message: str = "Resource not found"
    http_status: int = 404
    resource_type: str = ""
    resource_id: str = ""
    
    def __post_init__(self) -> None:
        if self.resource_type:
            self.details["resource_type"] = self.resource_type
        if self.resource_id:
            self.details["resource_id"] = self.resource_id


@dataclass
class ConflictError(AutoHelperError):
    """Operation conflicts with current state."""
    
    code: str = "CONFLICT"
    message: str = "Operation conflicts with current state"
    http_status: int = 409


@dataclass
class ValidationError(AutoHelperError):
    """Request validation failed."""
    
    code: str = "VALIDATION"
    message: str = "Validation error"
    http_status: int = 400
