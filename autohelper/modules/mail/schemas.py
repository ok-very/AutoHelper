"""
Mail module Pydantic schemas for request/response models.
"""

from datetime import datetime
from typing import Any, Literal

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
# TRIAGE / ENRICHMENT
# =============================================================================

TriageStatus = Literal["pending", "action_required", "informational", "archived"]
Priority = Literal["low", "medium", "high", "urgent"]


class TriageInfo(BaseModel):
    """AI-generated triage information."""
    status: TriageStatus = "pending"
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    reasoning: str | None = None
    suggested_action: str | None = None


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


class EnrichedTransientEmail(BaseModel):
    """Extended transient email with AI analysis."""
    # Base fields
    id: str
    subject: str | None
    sender: str | None
    received_at: datetime | None
    project_id: str | None
    body_preview: str | None
    metadata: dict[str, Any] | None = None
    ingestion_id: int | None = None
    created_at: datetime | None = None

    # Enriched fields
    triage: TriageInfo | None = None
    priority: Priority = "medium"
    priority_factors: list[str] = Field(default_factory=list)
    extracted_keywords: list[str] = Field(default_factory=list)
    has_attachments: bool = False
    thread_count: int = 1


class TransientEmailList(BaseModel):
    """List of transient emails with pagination."""
    emails: list[TransientEmail]
    total: int
    limit: int
    offset: int


# =============================================================================
# TRIAGE ACTIONS
# =============================================================================

class UpdateTriageRequest(BaseModel):
    """Request to update email triage status."""
    status: TriageStatus
    notes: str | None = None


class TriageActionResponse(BaseModel):
    """Response from triage action."""
    status: str
    email_id: str
    triage_status: TriageStatus
    triaged_at: str


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
