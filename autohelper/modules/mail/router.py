"""
Mail module API routes.
"""

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from autohelper.config import get_settings
from autohelper.db import get_db
from autohelper.modules.mail.schemas import (
    IngestionLogEntry,
    IngestionLogList,
    IngestRequest,
    IngestResponse,
    MailServiceStatus,
    TransientEmail,
    TransientEmailList,
    TriageRequest,
    TriageResponse,
)
from autohelper.modules.mail.service import MailService

router = APIRouter(prefix="/mail", tags=["mail"])

# Column list shared by list and get queries
_EMAIL_COLUMNS = """
    id, subject, sender, received_at, project_id, body_preview,
    metadata, ingestion_id, created_at, triage_status, triage_notes, triaged_at
"""


def _row_to_email(row: tuple[str, ...]) -> TransientEmail:
    """Convert a database row to a TransientEmail model."""
    from datetime import datetime

    metadata = None
    if row[6]:
        try:
            metadata = json.loads(row[6])
        except (json.JSONDecodeError, TypeError):
            metadata = None

    # Parse datetime strings if present
    received_at = datetime.fromisoformat(row[3]) if row[3] else None
    created_at = datetime.fromisoformat(row[8]) if row[8] else None

    return TransientEmail(
        id=row[0],
        subject=row[1],
        sender=row[2],
        received_at=received_at,
        project_id=row[4],
        body_preview=row[5],
        metadata=metadata,
        ingestion_id=int(row[7]) if row[7] else None,
        created_at=created_at,
        triage_status=row[9],
        triage_notes=row[10],
        triaged_at=row[11],
    )


VALID_TRIAGE_STATUSES = {"pending", "action_required", "informational", "archived"}


@router.get("/status", response_model=MailServiceStatus)
async def get_status() -> MailServiceStatus:
    """Get current mail service status."""
    settings = get_settings()
    svc = MailService()

    return MailServiceStatus(
        enabled=settings.mail_enabled,
        running=svc.running,
        poll_interval=settings.mail_poll_interval,
        output_path=str(settings.mail_output_path),
        ingest_path=str(settings.mail_ingest_path),
    )


@router.post("/start")
async def start_service() -> dict[str, str]:
    """Start the mail polling service."""
    svc = MailService()
    # Reload settings in case they changed
    svc.settings = get_settings()
    svc.start()
    return {"status": "started" if svc.running else "disabled"}


@router.post("/stop")
async def stop_service() -> dict[str, str]:
    """Stop the mail polling service."""
    svc = MailService()
    svc.stop()
    return {"status": "stopped"}


@router.get("/emails", response_model=TransientEmailList)
async def list_emails(
    project_id: str | None = Query(None, description="Filter by project ID"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> TransientEmailList:
    """List transient emails with optional filtering."""
    db = get_db()

    if project_id:
        count_sql = "SELECT COUNT(*) FROM transient_emails WHERE project_id = ?"
        total = db.execute(count_sql, (project_id,)).fetchone()[0]

        rows = db.execute(
            f"""
            SELECT {_EMAIL_COLUMNS}
            FROM transient_emails
            WHERE project_id = ?
            ORDER BY received_at DESC
            LIMIT ? OFFSET ?
        """,
            (project_id, limit, offset),
        ).fetchall()
    else:
        count_sql = "SELECT COUNT(*) FROM transient_emails"
        total = db.execute(count_sql).fetchone()[0]

        rows = db.execute(
            f"""
            SELECT {_EMAIL_COLUMNS}
            FROM transient_emails
            ORDER BY received_at DESC
            LIMIT ? OFFSET ?
        """,
            (limit, offset),
        ).fetchall()

    emails = [_row_to_email(row) for row in rows]

    return TransientEmailList(
        emails=emails,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/emails/{email_id}", response_model=TransientEmail)
async def get_email(email_id: str) -> TransientEmail:
    """Get a single transient email by ID."""
    db = get_db()

    row = db.execute(
        f"""
        SELECT {_EMAIL_COLUMNS}
        FROM transient_emails
        WHERE id = ?
    """,
        (email_id,),
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Email not found")

    return _row_to_email(row)


# =============================================================================
# TRIAGE ENDPOINTS
# =============================================================================


_UNSET = object()  # sentinel: distinguish "not provided" from explicit None


def _update_triage(
    email_id: str, status: str, notes: str | None | object = _UNSET
) -> TriageResponse:
    """Shared triage update logic.

    When *notes* is ``_UNSET`` (the default), existing ``triage_notes`` are
    preserved.  Pass an explicit value (including ``None``) to overwrite.
    """
    if status not in VALID_TRIAGE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid triage status: {status}. Must be one of {VALID_TRIAGE_STATUSES}",
        )

    db = get_db()

    # Verify email exists
    row = db.execute(
        "SELECT id FROM transient_emails WHERE id = ?", (email_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Email not found")

    now = datetime.now(timezone.utc).isoformat()

    if notes is _UNSET:
        # Preserve existing triage_notes
        db.execute(
            """
            UPDATE transient_emails
            SET triage_status = ?, triaged_at = ?
            WHERE id = ?
        """,
            (status, now, email_id),
        )
    else:
        db.execute(
            """
            UPDATE transient_emails
            SET triage_status = ?, triage_notes = ?, triaged_at = ?
            WHERE id = ?
        """,
            (status, notes, now, email_id),
        )
    db.commit()

    return TriageResponse(
        status="ok",
        email_id=email_id,
        triage_status=status,
        triaged_at=now,
    )


@router.post("/emails/{email_id}/triage", response_model=TriageResponse)
async def triage_email(email_id: str, request: TriageRequest) -> TriageResponse:
    """Set triage status and optional notes on an email."""
    return _update_triage(email_id, request.status, request.notes)


@router.post("/emails/{email_id}/archive", response_model=TriageResponse)
async def archive_email(email_id: str) -> TriageResponse:
    """Shorthand to set triage_status = 'archived'. Preserves existing notes."""
    return _update_triage(email_id, "archived")


@router.post("/emails/{email_id}/mark-action-required", response_model=TriageResponse)
async def mark_action_required(email_id: str) -> TriageResponse:
    """Shorthand to set triage_status = 'action_required'. Preserves existing notes."""
    return _update_triage(email_id, "action_required")


@router.post("/emails/{email_id}/mark-informational", response_model=TriageResponse)
async def mark_informational(email_id: str) -> TriageResponse:
    """Shorthand to set triage_status = 'informational'. Preserves existing notes."""
    return _update_triage(email_id, "informational")


# =============================================================================
# INGESTION
# =============================================================================


@router.get("/ingestion-log", response_model=IngestionLogList)
async def list_ingestion_log(
    limit: int = Query(50, ge=1, le=500),
) -> IngestionLogList:
    """List PST/OST ingestion history."""
    db = get_db()

    total = db.execute("SELECT COUNT(*) FROM mail_ingestion_log").fetchone()[0]

    rows = db.execute(
        """
        SELECT id, source_path, ingested_at, email_count, status, error_message
        FROM mail_ingestion_log
        ORDER BY ingested_at DESC
        LIMIT ?
    """,
        (limit,),
    ).fetchall()

    entries = [
        IngestionLogEntry(
            id=row[0],
            source_path=row[1],
            ingested_at=row[2],
            email_count=row[3] or 0,
            status=row[4],
            error_message=row[5],
        )
        for row in rows
    ]

    return IngestionLogList(entries=entries, total=total)


@router.post("/ingest", response_model=IngestResponse)
async def ingest_pst(request: IngestRequest) -> IngestResponse:
    """
    Ingest a PST/OST file.

    Security: File must be located under the configured mail_ingest_path
    and have a .pst or .ost extension.
    """
    svc = MailService()
    result = svc.ingest_pst(request.file_path)

    return IngestResponse(
        success=result.get("success", False),
        count=result.get("count"),
        error=result.get("error"),
    )
