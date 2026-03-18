"""
Index module API schemas.
"""

from datetime import datetime

from pydantic import BaseModel


class IndexStats(BaseModel):
    """Statistics for an index run."""

    added: int
    updated: int
    removed: int
    errors: int
    total_size: int
    duration_ms: int


class RebuildRequest(BaseModel):
    """Request to rebuild index."""

    roots: list[str] | None = None  # Specific root IDs to rebuild (None = all)
    force_hash: bool = False  # Force re-hashing even if timestamps match


class RunResponse(BaseModel):
    """Response for index operations."""

    run_id: str
    status: str
    started_at: datetime
