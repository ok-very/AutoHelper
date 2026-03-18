"""Contact Sync module Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel


class ContactStatusResponse(BaseModel):
    """Response for GET /contacts/status."""

    enabled: bool
    last_sync: datetime | None
    next_sync: datetime | None
    last_status: str | None  # "completed", "failed", "skipped", "dry_run"
    last_file_hash: str | None
    csv_path: str
    is_running: bool


class ContactSyncTriggerResponse(BaseModel):
    """Response for POST /contacts/sync."""

    status: str
    message: str


class ContactHistoryEntry(BaseModel):
    """Single entry in the sync history log."""

    sync_id: str
    started_at: str
    completed_at: str | None
    status: str
    created: int
    updated: int
    deleted: int
    unchanged: int
    errors: list[str]
    dry_run: bool
    file_hash: str
    csv_row_count: int
    duration_ms: int


class ContactHistoryResponse(BaseModel):
    """Response for GET /contacts/history."""

    entries: list[ContactHistoryEntry]
