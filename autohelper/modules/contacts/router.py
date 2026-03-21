"""Contact module routes — sync endpoints + hub CRUD + association management."""

import asyncio
import json
from dataclasses import asdict

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from autohelper.config import get_settings
from autohelper.db import get_db

from .scheduler import get_next_contact_sync_time
from .schemas import (
    ContactHistoryEntry,
    ContactHistoryResponse,
    ContactStatusResponse,
    ContactSyncTriggerResponse,
)
from .exchange_sync import test_exchange_connection, disconnect_exchange
from .service import ContactSyncService
from . import hub

router = APIRouter(prefix="/contacts", tags=["contacts"])


# ── Sync endpoints (existing) ────────────────────────────────────


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


@router.get("/exchange/status")
async def exchange_status() -> dict:
    """Return current Exchange session state (disconnected|connecting|connected)."""
    from .exchange_sync import get_session_state
    return get_session_state()


@router.get("/exchange/prerequisites")
async def exchange_prerequisites() -> dict:
    """Check if Exchange sync prerequisites are met (pwsh + module)."""
    from .exchange_sync import check_exchange_prerequisites
    return await asyncio.to_thread(check_exchange_prerequisites)


@router.post("/exchange/connect")
async def connect_exchange() -> dict:
    """Launch interactive Exchange login window for MFA authentication."""
    from .exchange_sync import connect_exchange_interactive
    return await asyncio.to_thread(connect_exchange_interactive)


@router.post("/exchange/test")
async def test_exchange() -> dict:
    """Test Exchange Online connectivity (non-interactive)."""
    return await asyncio.to_thread(test_exchange_connection)


@router.post("/exchange/disconnect")
async def disconnect_exchange_endpoint() -> dict:
    """Disconnect active Exchange Online session."""
    return await asyncio.to_thread(disconnect_exchange)


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


# ── Hub endpoints ────────────────────────────────────────────────


@router.get("/hub")
async def search_contacts_endpoint(
    q: str = Query("", description="Search by name, email, or company"),
    category: str = Query("", description="Filter by category"),
    staleness: str = Query("", description="Filter by staleness label"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    """Search contacts in the hub."""
    result = hub.search_contacts(
        query=q, category=category, staleness=staleness,
        limit=limit, offset=offset,
    )
    return {
        "contacts": [asdict(c) for c in result.contacts],
        "total": result.total,
        "offset": result.offset,
        "limit": result.limit,
    }


@router.get("/hub/categories")
async def list_categories_endpoint() -> list[dict]:
    """Return distinct categories with counts."""
    return hub.list_categories()


@router.get("/hub/count")
async def get_count() -> dict:
    """Return total contact count."""
    return {"count": hub.get_contact_count()}


@router.get("/hub/{contact_id}")
async def get_contact_endpoint(contact_id: str) -> dict:
    """Get a single contact by ID."""
    contact = hub.get_contact(contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    associations = hub.get_contact_projects(contact_id)
    return {
        **asdict(contact),
        "associations": [asdict(a) for a in associations],
    }


@router.post("/hub")
async def create_contact_endpoint(body: dict) -> dict:
    """Create a new contact."""
    try:
        contact = hub.create_contact(**body)
        return asdict(contact)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/hub/{contact_id}")
async def update_contact_endpoint(contact_id: str, body: dict) -> dict:
    """Update a contact."""
    contact = hub.update_contact(contact_id, **body)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return asdict(contact)


@router.delete("/hub/{contact_id}")
async def delete_contact_endpoint(contact_id: str) -> dict:
    """Delete a contact."""
    if not hub.delete_contact(contact_id):
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"deleted": True}


# ── Association endpoints ────────────────────────────────────────


@router.get("/hub/{contact_id}/projects")
async def get_contact_projects_endpoint(contact_id: str) -> list[dict]:
    """Get all project associations for a contact."""
    return [asdict(a) for a in hub.get_contact_projects(contact_id)]


@router.get("/projects/{project_id}/contacts")
async def get_project_contacts_endpoint(project_id: str) -> list[dict]:
    """Get all contacts associated with a project."""
    return [asdict(a) for a in hub.get_project_contacts(project_id)]


@router.post("/projects/{project_id}/contacts")
async def associate_contact_endpoint(project_id: str, body: dict) -> dict:
    """Associate a contact with a project."""
    try:
        assoc = hub.associate_contact(
            contact_id=body["contact_id"],
            project_id=project_id,
            role=body["role"],
            is_primary=body.get("is_primary", True),
            notes=body.get("notes"),
        )
        return asdict(assoc)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/associations/{association_id}")
async def remove_association_endpoint(association_id: str) -> dict:
    """Remove a project-contact association."""
    if not hub.remove_association(association_id):
        raise HTTPException(status_code=404, detail="Association not found")
    return {"deleted": True}


# ── Import endpoint ──────────────────────────────────────────────


@router.post("/hub/import")
async def import_contacts_endpoint(
    background_tasks: BackgroundTasks,
    body: dict | None = None,
) -> dict:
    """Import contacts from CSV into the hub."""
    from .import_csv import import_contacts_csv

    settings = get_settings()
    csv_path = (body or {}).get("csv_path", settings.contact_sync_csv_path)
    overrides_path = (body or {}).get("overrides_path")
    dry_run = (body or {}).get("dry_run", False)

    if dry_run:
        result = import_contacts_csv(csv_path, overrides_path, dry_run=True)
        return {
            "dry_run": True,
            "total_csv_rows": result.total_csv_rows,
            "would_create": result.created,
        }

    # Run in background for large imports
    def _run_import():
        import_contacts_csv(csv_path, overrides_path, dry_run=False)

    background_tasks.add_task(_run_import)
    return {"status": "started", "message": "Contact import started in background"}


# ── Resolution endpoints ─────────────────────────────────────────


@router.get("/resolve/sender")
async def resolve_sender_endpoint(email: str = Query(...)) -> dict:
    """Resolve an email sender to a hub contact with project associations."""
    result = hub.resolve_sender(email)
    if not result:
        raise HTTPException(status_code=404, detail="Sender not found in hub")
    return result


@router.get("/resolve/project/{project_id}/merge-fields")
async def resolve_merge_fields_endpoint(project_id: str) -> dict:
    """Get merge fields for a project from the contact hub."""
    return hub.resolve_merge_fields(project_id)
