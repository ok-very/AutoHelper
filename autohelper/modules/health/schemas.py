"""Health module schemas."""

from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response."""
    
    status: str
    timestamp: datetime
    version: str


class RootStatus(BaseModel):
    """Status of a configured root."""
    
    root_id: str
    path: str
    enabled: bool
    accessible: bool
    file_count: int


class IndexStatus(BaseModel):
    """Index status summary."""
    
    last_run_id: str | None
    last_run_at: datetime | None
    last_run_status: str | None
    total_files: int
    total_roots: int


class MigrationStatus(BaseModel):
    """Migration status."""
    
    applied_count: int
    pending_count: int


class StatusResponse(BaseModel):
    """Full status response."""
    
    status: str
    version: str
    timestamp: datetime
    debug: bool
    db_path: str
    db_reachable: bool
    migrations: MigrationStatus
    index: IndexStatus
    roots: list[RootStatus]
