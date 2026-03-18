"""Artist Records API routes."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from starlette.responses import StreamingResponse

from .config import get_lexicon, save_lexicon, reset_lexicon, _parse_lexicon, _serialize_lexicon
from .service import get_artist_service

router = APIRouter(prefix="/artists", tags=["artists"])


# ------------------------------------------------------------------
# List & search
# ------------------------------------------------------------------

@router.get("")
async def list_artists(
    q: str = "",
    category: str = "",
    min_completeness: float = Query(0.0, ge=0.0, le=1.0),
    max_completeness: float = Query(1.0, ge=0.0, le=1.0),
    review_status: str = "",
    nation: str = "",
    offset: int = Query(0, ge=0),
    limit: int = Query(5000, ge=1, le=10000),
) -> list[dict[str, Any]]:
    """Query cached artist data with filters."""
    svc = get_artist_service()
    return svc.get_artists(
        q=q,
        category=category,
        min_completeness=min_completeness,
        max_completeness=max_completeness,
        review_status=review_status,
        nation=nation,
        offset=offset,
        limit=limit,
    )


@router.get("/stats")
async def get_stats() -> dict[str, Any]:
    """Aggregate statistics for the dashboard header."""
    return get_artist_service().get_stats()


# ------------------------------------------------------------------
# Scan operations (fixed paths — must precede /{artist_id})
# ------------------------------------------------------------------

@router.post("/scan")
async def trigger_scan(background_tasks: BackgroundTasks) -> dict[str, str]:
    """Trigger a full artist scan (runs in background)."""
    svc = get_artist_service()
    if svc.is_scanning:
        raise HTTPException(status_code=409, detail="Scan already in progress")
    background_tasks.add_task(svc.full_scan)
    return {"status": "started", "message": "Full scan started in background"}


@router.get("/scan/status")
async def scan_status() -> dict[str, Any]:
    """Current scan status and last run info."""
    return get_artist_service().get_scan_status()


@router.post("/scan/stop")
async def stop_scan() -> dict[str, str]:
    """Stop a running scan after the current artist finishes."""
    svc = get_artist_service()
    if not svc.is_scanning:
        raise HTTPException(status_code=409, detail="No scan in progress")
    svc.stop_scan()
    return {"status": "stopping"}


@router.get("/scan/log")
async def scan_log_stream():
    """SSE stream of scan progress lines."""
    svc = get_artist_service()

    async def event_generator():
        cursor = 0
        while True:
            lines, cursor = svc.get_scan_log(cursor)
            for line in lines:
                yield f"data: {line}\n\n"
            if not svc.is_scanning and not lines:
                yield "data: [done]\n\n"
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ------------------------------------------------------------------
# File operations (fixed path — must precede /{artist_id})
# ------------------------------------------------------------------

@router.get("/open-file")
async def open_file(path: str = Query(...)) -> dict[str, str]:
    """Open a file with the system default application (Windows)."""
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="File not found")
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", path])
    return {"status": "ok"}


# ------------------------------------------------------------------
# Lexicon configuration (fixed paths — must precede /{artist_id})
# ------------------------------------------------------------------

@router.get("/lexicon")
async def get_lexicon_config() -> dict[str, Any]:
    """Current lexicon configuration (identity options, weights, etc.)."""
    lex = get_lexicon()
    return _serialize_lexicon(lex)


@router.put("/lexicon")
async def update_lexicon_config(body: dict[str, Any]) -> dict[str, str]:
    """Update lexicon configuration. Validates and persists to disk."""
    try:
        lex = _parse_lexicon(body)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid lexicon: {e}")
    save_lexicon(lex)
    reset_lexicon()  # Force reload on next access
    return {"status": "ok"}


# ------------------------------------------------------------------
# Health report (fixed path — must precede /{artist_id})
# ------------------------------------------------------------------

@router.get("/health")
async def get_health_report() -> dict[str, Any]:
    """Health report: completeness ranking, gap analysis, broken items, enrichment opps."""
    return get_artist_service().get_health_report()


# ------------------------------------------------------------------
# Reconciliation (fixed paths — must precede /{artist_id})
# ------------------------------------------------------------------

@router.get("/reconciliation")
async def get_reconciliation() -> dict[str, Any]:
    """Reconciliation report: engagement pipeline + data quality (duplicates, variants, conflicts)."""
    from .reconciliation import get_reconciliation_report
    return get_reconciliation_report()


@router.post("/reconciliation/resolve")
async def resolve_reconciliation(body: dict[str, Any]) -> dict[str, str]:
    """Resolve a reconciliation item (link, dismiss, advance, merge)."""
    from .reconciliation import resolve_reconciliation_item
    action = body.get("action")
    if not action:
        raise HTTPException(status_code=400, detail="Missing action")
    resolve_reconciliation_item(body)
    return {"status": "ok"}


@router.post("/reconciliation/merge")
async def merge_artists_endpoint(body: dict[str, Any]) -> dict[str, Any]:
    """Merge two artist records: keep one, fold the other into it."""
    from .reconciliation import merge_artists
    keep_id = body.get("keep_id")
    remove_id = body.get("remove_id")
    if not keep_id or not remove_id:
        raise HTTPException(status_code=400, detail="Missing keep_id or remove_id")
    try:
        return merge_artists(keep_id, remove_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/reconciliation/auto-merge")
async def auto_merge_endpoint(body: dict[str, Any]) -> dict[str, Any]:
    """Auto-merge high-confidence duplicate pairs."""
    from .reconciliation import auto_merge
    threshold = body.get("threshold", 0.95)
    dry_run = body.get("dry_run", True)
    return auto_merge(threshold=threshold, dry_run=dry_run)


# ------------------------------------------------------------------
# Admin files (unattributed files from non-artist folders)
# ------------------------------------------------------------------

@router.get("/admin-files")
async def get_admin_files() -> list[dict]:
    """List unattributed admin files with candidate matches."""
    return get_artist_service().get_admin_files()


@router.post("/admin-files/{file_id}/attribute")
async def attribute_file(file_id: str, body: dict[str, Any]) -> dict[str, str]:
    """Manually attribute an admin file to an artist."""
    artist_id = body.get("artist_id")
    if not artist_id:
        raise HTTPException(status_code=400, detail="Missing artist_id")
    return get_artist_service().attribute_file(file_id, artist_id)


# ------------------------------------------------------------------
# Single artist (parameterised — must come after all fixed paths)
# ------------------------------------------------------------------

@router.get("/{artist_id}")
async def get_artist(artist_id: str) -> dict[str, Any]:
    """Full manifest for one artist."""
    result = get_artist_service().get_artist(artist_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Artist not found")
    return result


@router.get("/{artist_id}/bio-content")
async def get_bio_content(artist_id: str) -> dict[str, Any]:
    """Read inline bio text from the current bio file."""
    text = get_artist_service().get_bio_content(artist_id)
    if text is None:
        return {"content": None}
    return {"content": text}


@router.put("/{artist_id}/review")
async def update_review(artist_id: str, body: dict[str, str]) -> dict[str, str]:
    """Update review status for an artist."""
    status = body.get("status", "")
    if status not in ("pending", "approved", "flagged", "rejected"):
        raise HTTPException(status_code=400, detail="Invalid status")
    get_artist_service().update_review(artist_id, status)
    return {"status": "ok"}


@router.put("/{artist_id}/manifest")
async def save_manifest(artist_id: str, body: dict[str, Any]) -> dict[str, str]:
    """Save edited manifest fields (contact, identity, etc.) to disk and DB."""
    get_artist_service().save_manifest(artist_id, body)
    return {"status": "ok"}


@router.post("/{artist_id}/resolve-note")
async def resolve_note(artist_id: str, body: dict[str, Any]) -> dict[str, str]:
    """Remove a review note by index."""
    idx = body.get("index")
    if idx is None or not isinstance(idx, int):
        raise HTTPException(status_code=400, detail="Missing or invalid index")
    get_artist_service().resolve_note(artist_id, idx)
    return {"status": "ok"}


@router.post("/{artist_id}/panel")
async def add_panel_entry(artist_id: str, body: dict[str, Any]) -> dict[str, str]:
    """Append a panel entry (selection panel, community advisor, etc.)."""
    get_artist_service().add_panel_entry(artist_id, body)
    return {"status": "ok"}


@router.post("/{artist_id}/project")
async def add_project(artist_id: str, body: dict[str, Any]) -> dict[str, str]:
    """Append a public art project entry."""
    get_artist_service().add_project(artist_id, body)
    return {"status": "ok"}


@router.put("/{artist_id}/project/{project_index}/status")
async def update_project_status(
    artist_id: str, project_index: int, body: dict[str, Any]
) -> dict[str, str]:
    """Advance a project through pipeline stages."""
    status = body.get("status", "")
    valid = {"submitted", "longlisted", "shortlisted", "awarded", "completed"}
    if status not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(sorted(valid))}")
    get_artist_service().update_project_status(
        artist_id, project_index, status, body.get("status_date")
    )
    return {"status": "ok"}


@router.post("/{artist_id}/rescan")
async def rescan_artist(artist_id: str) -> dict[str, Any]:
    """Re-scan all folders for one artist."""
    return get_artist_service().rescan_artist(artist_id)


@router.get("/{artist_id}/open-folder")
async def open_folder(artist_id: str) -> dict[str, str]:
    """Open the primary folder for an artist in the file explorer."""
    manifest = get_artist_service().get_artist(artist_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Artist not found")

    primary = None
    for fl in manifest.get("folder_locations", []):
        if fl.get("is_primary"):
            primary = fl.get("folder_path")
            break
    if not primary or not os.path.isdir(primary):
        raise HTTPException(status_code=404, detail="Primary folder not found")

    if sys.platform == "win32":
        subprocess.Popen(["explorer", primary])
    else:
        subprocess.Popen(["xdg-open", primary])
    return {"status": "ok"}
