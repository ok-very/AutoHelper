"""File watch Pydantic schemas."""

import enum
from datetime import datetime

from pydantic import BaseModel, Field


class FileEventType(str, enum.Enum):
    """Types of filesystem events."""

    CREATED = "file_created"
    DELETED = "file_deleted"
    MOVED = "file_moved"


class FileWatchEvent(BaseModel):
    """A detected filesystem event."""

    event_type: FileEventType
    path: str
    old_path: str | None = None  # Only for MOVED events
    ref_id: str | None = None  # If path matches a known reference
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    root_id: str


class WatchRootConfig(BaseModel):
    """Configuration for watching a root directory."""

    root_id: str
    path: str


class DrainResponse(BaseModel):
    """Response from draining events."""

    events: list[FileWatchEvent]
    count: int
