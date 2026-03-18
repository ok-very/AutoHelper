"""Contact Sync module routes."""

import json

from fastapi import APIRouter, BackgroundTasks, HTTPException

from autohelper.config import get_settings
from autohelper.db import get_db

from .scheduler import get_next_contact_sync_time
from .schemas import (
    ContactHistoryEntry,
    ContactHistoryResponse,
    ContactStatusResponse,
    ContactSyncTriggerResponse,
)
from .exchange_sync import test_exchange_connection
from .service import ContactSyncService

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("/status", response_model=ContactStatusResponse)
async def get_contact_status() -> ContactStatusResponse:
    """Get contact sync status."""
    settings = get_settings()
    service = ContactSyncService()

    last_sync_at = None
    last_status = None
    last_file_hash = None

    try:
        db = get_db()
        row = db.execute(
            "SELECT last_sync_at, last_status, file_hash FROM contact_sync_state WHERE id = 1"
        ).fetchone()
        if row:
            last_sync_at = row[0]
            last_status = row[1]
            last_file_hash = row[2]
    except Exception:
        pass

    return ContactStatusResponse(
        enabled=settings.contact_sync_enabled,
        last_sync=last_sync_at or service.last_sync,
        next_sync=get_next_contact_sync_time(),
        last_status=last_status,
        last_file_hash=last_file_hash,
        csv_path=settings.contact_sync_csv_path,
        is_running=service.is_running,
    )


@router.post("/sync", response_model=ContactSyncTriggerResponse)
async def trigger_sync(background_tasks: BackgroundTasks) -> ContactSyncTriggerResponse:
    """Trigger a manual contact sync (runs in background)."""
    service = ContactSyncService()

    if service.is_running:
        raise HTTPException(status_code=409, detail="Contact sync is already running")

    background_tasks.add_task(service.run_sync, True)  # force=True for manual trigger

    return ContactSyncTriggerResponse(
        status="started",
        message="Contact sync started in background",
    )


@router.post("/exchange/test")
async def test_exchange() -> dict:
    """Test Exchange Online connectivity via interactive OAuth."""
    return test_exchange_connection()


@router.get("/history", response_model=ContactHistoryResponse)
async def get_contact_history() -> ContactHistoryResponse:
    """Get recent contact sync history (last 20 runs)."""
    try:
        db = get_db()
        rows = db.execute(
            """SELECT sync_id, started_at, completed_at, status, created, updated,
                      deleted, unchanged, errors_json, dry_run, file_hash,
                      csv_row_count, duration_ms
               FROM contact_sync_log
               ORDER BY started_at DESC
               LIMIT 20"""
        ).fetchall()
    except Exception:
        return ContactHistoryResponse(entries=[])

    entries = []
    for row in rows:
        errors = []
        try:
            errors = json.loads(row[8]) if row[8] else []
        except Exception:
            pass

        entries.append(
            ContactHistoryEntry(
                sync_id=row[0],
                started_at=row[1],
                completed_at=row[2],
                status=row[3],
                created=row[4],
                updated=row[5],
                deleted=row[6],
                unchanged=row[7],
                errors=errors,
                dry_run=bool(row[9]),
                file_hash=row[10] or "",
                csv_row_count=row[11],
                duration_ms=row[12],
            )
        )

    return ContactHistoryResponse(entries=entries)
