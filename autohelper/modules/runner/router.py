"""
Runner module API routes.
"""

import asyncio
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from autohelper.shared.logging import get_logger

from .schemas import RunnerInvokeRequest, RunnerProgress, RunnerResult, RunnerStatus
from .service import RunnerService

logger = get_logger(__name__)

router = APIRouter(prefix="/runner", tags=["runner"])


# =============================================================================
# STATUS
# =============================================================================

@router.get("/status", response_model=RunnerStatus)
def get_status() -> RunnerStatus:
    """Get current runner service status."""
    service = RunnerService()
    return service.status


# =============================================================================
# INVOKE
# =============================================================================

@router.post("/invoke", response_model=RunnerResult)
async def invoke_runner(request: RunnerInvokeRequest) -> RunnerResult:
    """
    Invoke a runner synchronously and return the result.
    
    For streaming progress, use POST /invoke/stream instead.
    """
    service = RunnerService()
    result = await service.invoke(request)
    
    if not result.success and result.error:
        # Log error but don't expose internal details
        logger.warning(f"Runner invocation failed: {result.error}")
    
    return result


@router.post("/invoke/stream")
async def invoke_runner_stream(request: RunnerInvokeRequest) -> StreamingResponse:
    """
    Invoke a runner with streaming progress updates.
    
    Returns Server-Sent Events (SSE) stream with progress updates,
    followed by the final result.
    """
    service = RunnerService()
    
    async def event_generator() -> AsyncGenerator[str, None]:
        progress_queue: asyncio.Queue[RunnerProgress | None] = asyncio.Queue()
        result_holder: list[RunnerResult] = []
        
        def on_progress(progress: RunnerProgress):
            asyncio.get_event_loop().call_soon_threadsafe(
                progress_queue.put_nowait, progress
            )
        
        async def run_task():
            result = await service.invoke(request, on_progress=on_progress)
            result_holder.append(result)
            await progress_queue.put(None)  # Signal completion
        
        # Start runner task
        task = asyncio.create_task(run_task())
        
        try:
            # Stream progress updates
            while True:
                progress = await progress_queue.get()
                if progress is None:
                    break
                
                # Format as SSE
                yield f"event: progress\n"
                yield f"data: {progress.model_dump_json()}\n\n"
            
            # Send final result
            if result_holder:
                result = result_holder[0]
                yield f"event: result\n"
                yield f"data: {result.model_dump_json()}\n\n"
        
        finally:
            await task
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
