"""Index module routes."""

from fastapi import APIRouter, BackgroundTasks, HTTPException

from autohelper.shared.errors import ConflictError

from .schemas import (
    IndexRunResponse,
    IndexStatusResponse,
    RebuildRequest,
    RescanRequest,
    RootStats,
)
from .service import IndexService

router = APIRouter(prefix="/index", tags=["index"])


@router.post("/rebuild", response_model=dict)
async def rebuild_index(
    request: RebuildRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """
    Trigger a full index rebuild.
    
    Crawls all configured roots (or specified ones) and updates the index.
    Returns immediately with run ID; check /index/status for progress.
    """
    service = IndexService()
    
    try:
        # Run synchronously for now (could be background task for very large dirs)
        result = service.rebuild(
            root_ids=request.root_ids,
            include_hash=request.include_content_hash,
            max_hash_size=request.max_file_size_mb * 1024 * 1024,
        )
        return result
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=e.to_dict()) from e


@router.post("/rescan", response_model=dict)
async def rescan_index(request: RescanRequest) -> dict:
    """
    Trigger an incremental rescan.
    
    Checks for changed files using stat comparison.
    Faster than full rebuild for large directories.
    """
    service = IndexService()
    
    try:
        result = service.rescan(root_ids=request.root_ids)
        return result
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=e.to_dict()) from e


@router.get("/status", response_model=IndexStatusResponse)
async def get_index_status() -> IndexStatusResponse:
    """
    Get current index status.
    
    Returns whether indexing is running, last completed run, and counts.
    """
    service = IndexService()
    status = service.get_status()
    
    return IndexStatusResponse(
        is_running=status["is_running"],
        current_run=_to_run_response(status["current_run"]) if status["current_run"] else None,
        last_completed=(
            _to_run_response(status["last_completed"]) if status["last_completed"] else None
        ),
        total_roots=status["total_roots"],
        total_files=status["total_files"],
    )


@router.get("/roots", response_model=list[RootStats])
async def get_root_stats() -> list[RootStats]:
    """Get statistics for each indexed root."""
    service = IndexService()
    stats = service.get_root_stats()
    
    return [RootStats(**s) for s in stats]


def _to_run_response(run: dict) -> IndexRunResponse:
    """Convert run dict to response model."""
    from datetime import datetime
    
    return IndexRunResponse(
        index_run_id=run["index_run_id"],
        kind=run["kind"],
        status=run["status"],
        started_at=datetime.fromisoformat(run["started_at"]),
        finished_at=datetime.fromisoformat(run["finished_at"]) if run.get("finished_at") else None,
        stats=run.get("stats"),
    )
