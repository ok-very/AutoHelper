"""
Shared domain types used across modules.
Single source of truth - modules never import from each other.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any


class IndexRunStatus(str, Enum):
    """Status of an index run."""
    
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RequestContext:
    """Context attached to every request for traceability."""
    
    request_id: str
    work_item_id: str | None = None
    context_id: str | None = None
    actor: str = "system"
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    idempotency_key: str | None = None


@dataclass
class RootInfo:
    """Information about a configured root directory."""
    
    root_id: str
    path: Path
    enabled: bool
    created_at: datetime
    file_count: int = 0
    last_indexed_at: datetime | None = None


@dataclass
class FileInfo:
    """File metadata from the index."""
    
    file_id: str
    root_id: str
    canonical_path: str
    rel_path: str
    size: int
    mtime_ns: int
    content_hash: str | None
    indexed_at: datetime
    last_seen_at: datetime
    is_dir: bool
    ext: str
    mime: str | None = None


@dataclass
class OperationResult:
    """Result of a filesystem operation."""
    
    success: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    before_path: str | None = None
    after_path: str | None = None
