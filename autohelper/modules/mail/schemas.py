"""
Mail module Pydantic schemas for request/response models.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# =============================================================================
# STATUS
# =============================================================================

class MailServiceStatus(BaseModel):
    """Mail service status response."""
    enabled: bool
    running: bool
    poll_interval: int
    output_path: str
    ingest_path: str


# =============================================================================
# EMAILS
# =============================================================================

class TransientEmail(BaseModel):
    """Single transient email record."""
    id: str
    subject: str | None
    sender: str | None
    received_at: datetime | None
    project_id: str | None
    body_preview: str | None
    metadata: dict[str, Any] | None = None
    ingestion_id: int | None = None
    created_at: datetime | None = None


class TransientEmailList(BaseModel):
    """List of transient emails with pagination."""
    emails: list[TransientEmail]
    total: int
    limit: int
    offset: int


# =============================================================================
# INGESTION
# =============================================================================

class IngestionLogEntry(BaseModel):
    """Single ingestion log record."""
    id: int
    source_path: str
    ingested_at: datetime | None
    email_count: int
    status: str
    error_message: str | None = None


class IngestionLogList(BaseModel):
    """List of ingestion log entries."""
    entries: list[IngestionLogEntry]
    total: int


class IngestRequest(BaseModel):
    """Request to ingest a PST/OST file."""
    file_path: str = Field(..., description="Absolute path to the PST/OST file")


class IngestResponse(BaseModel):
    """Response from ingestion operation."""
    success: bool
    count: int | None = None
    error: str | None = None
