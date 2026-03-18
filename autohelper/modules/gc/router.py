"""Garbage Collection module routes."""

from fastapi import APIRouter, BackgroundTasks, HTTPException

from autohelper.config import get_settings
from autohelper.modules.context.autoart import AutoArtClient

from .scheduler import get_next_run_time, trigger_gc_now
from .schemas import (
    GCResultResponse,
    GCRunResponse,
    GCStatsResponse,
    GCStatusResponse,
    SessionStatsResponse,
)
from .service import GarbageCollectionService

router = APIRouter(prefix="/gc", tags=["gc"])


@router.get("/status", response_model=GCStatusResponse)
async def get_gc_status() -> GCStatusResponse:
    """
    Get garbage collection status.

    Returns:
    - Whether GC is enabled
    - Last run timestamp
    - Next scheduled run timestamp
    - Results from last cleanup
    """
    settings = get_settings()
    service = GarbageCollectionService()

    last_result = None
    if service.last_result:
        r = service.last_result
        last_result = GCResultResponse(
            started_at=r.started_at,
            completed_at=r.completed_at,
            status=r.status,
            rtf_files_deleted=r.rtf_files_deleted,
            rtf_bytes_freed=r.rtf_bytes_freed,
            manifests_cleaned=r.manifests_cleaned,
            mail_files_deleted=r.mail_files_deleted,
            import_sessions_deleted=r.import_sessions_deleted,
            export_sessions_deleted=r.export_sessions_deleted,
            errors=r.errors,
        )

    return GCStatusResponse(
        enabled=settings.gc_enabled,
        last_run=service.last_run,
        next_run=get_next_run_time(),
        last_result=last_result,
    )


@router.post("/run", response_model=GCRunResponse)
async def run_gc_now(background_tasks: BackgroundTasks) -> GCRunResponse:
    """
    Trigger an immediate garbage collection run.

    This runs in the background and returns immediately.
    Check /gc/status for results.
    """
    service = GarbageCollectionService()

    if service.is_running:
        raise HTTPException(
            status_code=409,
            detail="Garbage collection is already running",
        )

    # Run in background
    background_tasks.add_task(trigger_gc_now)

    return GCRunResponse(
        status="started",
        message="Garbage collection started in background",
    )


@router.get("/stats", response_model=GCStatsResponse)
async def get_gc_stats() -> GCStatsResponse:
    """
    Get garbage collection stats from backend.

    Returns stale session counts and oldest ages for monitoring.
    Proxies to backend /api/gc/stats endpoint.
    """
    settings = get_settings()
    client = AutoArtClient(
        api_url=settings.autoart_api_url,
        link_key=settings.autoart_link_key or None,
    )

    stats = client.get_gc_stats(retention_days=settings.gc_retention_days)

    if stats is None:
        raise HTTPException(
            status_code=502,
            detail="Failed to fetch GC stats from backend",
        )

    return GCStatsResponse(
        retention_days=stats.get("retention_days", settings.gc_retention_days),
        import_sessions=SessionStatsResponse(
            stale_count=stats.get("import_sessions", {}).get("stale_count", 0),
            oldest_age_days=stats.get("import_sessions", {}).get("oldest_age_days", 0),
        ),
        export_sessions=SessionStatsResponse(
            stale_count=stats.get("export_sessions", {}).get("stale_count", 0),
            oldest_age_days=stats.get("export_sessions", {}).get("oldest_age_days", 0),
        ),
    )
