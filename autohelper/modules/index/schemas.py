"""Index module schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class RebuildRequest(BaseModel):
    """Request to rebuild index."""
    
    root_ids: list[str] | None = Field(
        default=None,
        description="Specific roots to rebuild. If None, rebuilds all.",
    )
    include_content_hash: bool = Field(
        default=False,
        description="Compute content hashes (slower but enables dedup).",
    )
    max_file_size_mb: int = Field(
        default=100,
        description="Skip files larger than this for hashing.",
    )


class RescanRequest(BaseModel):
    """Request for incremental rescan."""
    
    root_ids: list[str] | None = None


class IndexRunResponse(BaseModel):
    """Response for index run status."""
    
    index_run_id: str
    kind: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    stats: dict | None = None


class IndexStatusResponse(BaseModel):
    """Overall index status."""
    
    is_running: bool
    current_run: IndexRunResponse | None = None
    last_completed: IndexRunResponse | None = None
    total_roots: int
    total_files: int


class RootStats(BaseModel):
    """Stats for a single root."""
    
    root_id: str
    path: str
    file_count: int
    dir_count: int
    total_size: int
    last_indexed_at: datetime | None = None
