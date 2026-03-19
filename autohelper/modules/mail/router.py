"""
Mail module API routes.
"""

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

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
    metadata, ingestion_id, created_at, triage_status, triage_notes, triaged_at, account
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
        account=row[12] if len(row) > 12 else "",
    )


VALID_TRIAGE_STATUSES = {"pending", "action_required", "informational", "archived"}


@router.get("/accounts")
async def list_accounts() -> list[str]:
    """List distinct account names from ingested emails."""
    db = get_db()
    rows = db.execute(
        "SELECT DISTINCT account FROM transient_emails WHERE account != '' ORDER BY account"
    ).fetchall()
    return [row[0] for row in rows]


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


@router.get("/scan-accounts")
async def scan_accounts() -> list[dict[str, str]]:
    """Discover Outlook accounts from the live COM installation."""
    from autohelper.shared.platform import can_use_outlook

    if not can_use_outlook():
        return []

    try:
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
            namespace = outlook.GetNamespace("MAPI")
            accounts: list[dict[str, str]] = []
            for i in range(namespace.Folders.Count):
                folder = namespace.Folders.Item(i + 1)
                name = getattr(folder, "Name", f"Account {i + 1}")
                # Check if it has an Inbox
                has_inbox = False
                try:
                    for j in range(folder.Folders.Count):
                        if getattr(folder.Folders.Item(j + 1), "Name", "").lower() == "inbox":
                            has_inbox = True
                            break
                except Exception:
                    pass
                accounts.append({"name": name, "has_inbox": str(has_inbox).lower()})
            return accounts
        finally:
            pythoncom.CoUninitialize()
    except Exception:
        return []


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
    account: str | None = Query(None, description="Filter by account/mailbox name"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> TransientEmailList:
    """List transient emails with optional filtering."""
    db = get_db()

    where_clauses: list[str] = []
    params: list[str | int] = []

    if project_id:
        where_clauses.append("project_id = ?")
        params.append(project_id)
    if account:
        where_clauses.append("account = ?")
        params.append(account)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    total = db.execute(
        f"SELECT COUNT(*) FROM transient_emails {where_sql}", params
    ).fetchone()[0]

    rows = db.execute(
        f"""
        SELECT {_EMAIL_COLUMNS}
        FROM transient_emails
        {where_sql}
        ORDER BY received_at DESC
        LIMIT ? OFFSET ?
    """,
        [*params, limit, offset],
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
    """Get a single transient email by ID, with body fetched from Outlook if available."""
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

    email = _row_to_email(row)

    # Try to fetch body from Outlook COM on demand
    from autohelper.shared.platform import can_use_outlook

    if can_use_outlook() and not email.body_preview:
        try:
            import pythoncom
            import win32com.client

            pythoncom.CoInitialize()
            try:
                outlook = win32com.client.Dispatch("Outlook.Application")
                namespace = outlook.GetNamespace("MAPI")
                item = namespace.GetItemFromID(email_id)
                if item:
                    email.body_preview = getattr(item, "Body", "")[:1000]
                    email.body_html = getattr(item, "HTMLBody", None)
            finally:
                pythoncom.CoUninitialize()
        except Exception:
            pass  # Body unavailable — that's fine, we still have the metadata

    return email


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

    # Best-effort sync: write triage category back to Outlook
    # This is a convenience — our DB is the source of truth
    _TRIAGE_CATEGORY_MAP = {
        "action_required": "BFA: Action Required",
        "informational": "BFA: FYI",
        "archived": "BFA: Archived",
    }
    category = _TRIAGE_CATEGORY_MAP.get(status)
    if category:
        try:
            from autohelper.modules.mail.service import sync_category_to_outlook
            sync_category_to_outlook(email_id, category)
        except Exception:
            pass  # Non-critical — Outlook sync is a convenience

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
# CLICKUP TASK LINKING
# =============================================================================


class LinkToTaskRequest(BaseModel):
    task_id: str
    auto_thread: bool = True


@router.post("/emails/{email_id}/link-task")
async def link_email_to_task(email_id: str, body: LinkToTaskRequest) -> dict[str, Any]:
    """Link an email to a ClickUp task by posting it as a comment.

    If auto_thread is True, stores the link so future emails in the same
    thread automatically get posted to the same task.
    """
    import json as _json

    db = get_db()

    # Fetch email record
    row = db.execute(
        f"SELECT {_EMAIL_COLUMNS} FROM transient_emails WHERE id = ?", (email_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Email not found")

    email = _row_to_email(row)

    # Build comment text
    lines = [
        f"**Email from {email.sender}**",
        f"**Subject:** {email.subject}",
        f"**Received:** {email.received_at}",
    ]
    if email.body_preview:
        lines.append(f"\n{email.body_preview[:500]}")

    comment_text = "\n".join(lines)

    # Post to ClickUp
    from autohelper.config import get_settings
    from autohelper.modules.clickup.client import ClickUp

    settings = get_settings()
    token = getattr(settings, "clickup_token", "")
    if not token:
        raise HTTPException(status_code=400, detail="ClickUp not configured")

    try:
        async with ClickUp(token) as cu:
            await cu.comments.create(body.task_id, comment_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to post comment: {e}") from e

    # Store the link in metadata for auto-threading
    metadata = email.metadata or {}
    metadata["linked_task_id"] = body.task_id
    if body.auto_thread and email.subject:
        # Store thread key for auto-matching future emails
        metadata["thread_key"] = _normalize_thread_key(email.subject)

    db.execute(
        "UPDATE transient_emails SET metadata = ? WHERE id = ?",
        (_json.dumps(metadata), email_id),
    )
    db.commit()

    return {
        "ok": True,
        "task_id": body.task_id,
        "auto_thread": body.auto_thread,
    }


def _normalize_thread_key(subject: str) -> str:
    """Normalize subject to a thread key by stripping RE:/FW: prefixes."""
    import re
    clean = re.sub(r"^(re|fw|fwd)\s*:\s*", "", subject.strip(), flags=re.IGNORECASE)
    return clean.strip().lower()


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


# =============================================================================
# DRAFT CREATION
# =============================================================================


class DraftCreateRequest(BaseModel):
    to: str = ""
    subject: str
    body: str
    cc: str | None = None


@router.post("/draft/create")
async def create_draft(request: DraftCreateRequest) -> dict[str, Any]:
    """Create an Outlook draft from composed content."""
    from autohelper.modules.mail.draft import (
        can_use_outlook,
        create_draft_via_com,
    )

    if can_use_outlook():
        try:
            result = create_draft_via_com(
                to=request.to,
                subject=request.subject,
                body=request.body,
                cc=request.cc,
            )
            return {"ok": True, "strategy": "outlook_com", **result}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # No Outlook available — return preview
    return {
        "ok": False,
        "strategy": "preview",
        "subject": request.subject,
        "html_body": request.body,
        "error": "Outlook COM not available — draft not created",
    }
