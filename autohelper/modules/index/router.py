"""
Index module API router.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from typing import Annotated, Any

from autohelper.shared.types import RequestContext
from autohelper.shared.errors import ConflictError
from .schemas import RebuildRequest, RunResponse
from .service import IndexService

router = APIRouter(prefix="/index", tags=["index"])

@router.post("/rebuild", response_model=RunResponse)
async def rebuild_index(
    request: RebuildRequest,
    background_tasks: BackgroundTasks,
    # request_context: Annotated[RequestContext, Depends(get_request_context)] # Future: proper context binding
) -> RunResponse:
    """
    Trigger a full index rebuild.
    
    Warning: This is a potentially heavy operation.
    """
    service = IndexService()
    
    # Check if already running? Service check handles concurrent runs via DB state or locking?
    # Our simple implementation allows concurrent runs but that might be bad for DB contention.
    # The tests expect 409 Conflict if running.
    status = service.get_status()
    if status["is_running"]:
        raise ConflictError(message="Index run already in progress")

    return service.rebuild_index(
        specific_root_id=request.roots[0] if request.roots else None, 
        force_hash=request.force_hash
    )

@router.post("/rescan", response_model=RunResponse)
async def rescan_index(
    request: RebuildRequest,
    background_tasks: BackgroundTasks,
) -> RunResponse:
    """Rescan index (alias for rebuild)."""
    service = IndexService()
    
    status = service.get_status()
    if status["is_running"]:
        raise ConflictError(message="Index run already in progress")
        
    return service.rescan()

@router.get("/status")
async def get_status() -> dict[str, Any]:
    """Get indexer status."""
    service = IndexService()
    return service.get_status()

@router.get("/roots")
async def get_roots() -> list[dict[str, Any]]:
    """Get configured roots and their stats."""
    service = IndexService()
    return service.get_roots_stats()
