"""
Mail module API routes.
"""

import json

from fastapi import APIRouter, HTTPException, Query

from autohelper.config import get_settings
from autohelper.db import get_db
from autohelper.modules.mail.service import MailService
from autohelper.modules.mail.schemas import (
    MailServiceStatus,
    TransientEmail,
    TransientEmailList,
    IngestionLogEntry,
    IngestionLogList,
    IngestRequest,
    IngestResponse,
)

router = APIRouter(prefix="/mail", tags=["mail"])


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

    # Use parameterized queries to avoid SQL injection
    # The where_clause only contains static SQL, user input goes through params
    if project_id:
        count_sql = "SELECT COUNT(*) FROM transient_emails WHERE project_id = ?"
        total = db.execute(count_sql, (project_id,)).fetchone()[0]

        rows = db.execute("""
            SELECT id, subject, sender, received_at, project_id, body_preview,
                   metadata, ingestion_id, created_at
            FROM transient_emails
            WHERE project_id = ?
            ORDER BY received_at DESC
            LIMIT ? OFFSET ?
        """, (project_id, limit, offset)).fetchall()
    else:
        count_sql = "SELECT COUNT(*) FROM transient_emails"
        total = db.execute(count_sql).fetchone()[0]

        rows = db.execute("""
            SELECT id, subject, sender, received_at, project_id, body_preview,
                   metadata, ingestion_id, created_at
            FROM transient_emails
            ORDER BY received_at DESC
            LIMIT ? OFFSET ?
        """, (limit, offset)).fetchall()

    emails = []
    for row in rows:
        metadata = None
        if row[6]:
            try:
                metadata = json.loads(row[6])
            except (json.JSONDecodeError, TypeError):
                metadata = None

        emails.append(TransientEmail(
            id=row[0],
            subject=row[1],
            sender=row[2],
            received_at=row[3],
            project_id=row[4],
            body_preview=row[5],
            metadata=metadata,
            ingestion_id=row[7],
            created_at=row[8],
        ))

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

    row = db.execute("""
        SELECT id, subject, sender, received_at, project_id, body_preview,
               metadata, ingestion_id, created_at
        FROM transient_emails
        WHERE id = ?
    """, (email_id,)).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Email not found")

    metadata = None
    if row[6]:
        try:
            metadata = json.loads(row[6])
        except (json.JSONDecodeError, TypeError):
            metadata = None

    return TransientEmail(
        id=row[0],
        subject=row[1],
        sender=row[2],
        received_at=row[3],
        project_id=row[4],
        body_preview=row[5],
        metadata=metadata,
        ingestion_id=row[7],
        created_at=row[8],
    )


@router.get("/ingestion-log", response_model=IngestionLogList)
async def list_ingestion_log(
    limit: int = Query(50, ge=1, le=500),
) -> IngestionLogList:
    """List PST/OST ingestion history."""
    db = get_db()

    total = db.execute("SELECT COUNT(*) FROM mail_ingestion_log").fetchone()[0]

    rows = db.execute("""
        SELECT id, source_path, ingested_at, email_count, status, error_message
        FROM mail_ingestion_log
        ORDER BY ingested_at DESC
        LIMIT ?
    """, (limit,)).fetchall()

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
