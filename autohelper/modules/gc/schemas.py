"""Garbage Collection module schemas."""

from datetime import datetime

from pydantic import BaseModel


class GCStatusResponse(BaseModel):
    """Response for GET /gc/status."""

    enabled: bool
    last_run: datetime | None
    next_run: datetime | None
    last_result: "GCResultResponse | None"


class GCResultResponse(BaseModel):
    """Cleanup result summary."""

    started_at: datetime
    completed_at: datetime | None
    status: str
    rtf_files_deleted: int
    rtf_bytes_freed: int
    manifests_cleaned: int
    mail_files_deleted: int
    import_sessions_deleted: int
    export_sessions_deleted: int
    errors: list[str]


class GCRunResponse(BaseModel):
    """Response for POST /gc/run."""

    status: str
    message: str


class GCStatsResponse(BaseModel):
    """Response for GET /gc/stats (proxied from backend)."""

    retention_days: int
    import_sessions: "SessionStatsResponse"
    export_sessions: "SessionStatsResponse"


class SessionStatsResponse(BaseModel):
    """Stats for a session type."""

    stale_count: int
    oldest_age_days: int


# Update forward references
GCStatusResponse.model_rebuild()
