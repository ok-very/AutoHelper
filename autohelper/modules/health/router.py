"""Health module routes."""

import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from autohelper.shared.logging import get_log_buffer, subscribe_logs, unsubscribe_logs

from .schemas import HealthResponse, StatusResponse
from .service import HealthService

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """
    Simple health check.

    Returns ok if the service is running.
    """
    service = HealthService()
    return service.get_health()


@router.get("/status", response_model=StatusResponse)
async def status() -> StatusResponse:
    """
    Detailed status check.

    Returns:
    - Database connectivity
    - Migration status
    - Configured roots and their accessibility
    - Last index run info
    """
    service = HealthService()
    return service.get_status()


@router.get("/logs")
async def get_logs() -> JSONResponse:
    """Return recent log entries from the ring buffer."""
    return JSONResponse(content={"entries": get_log_buffer()})


@router.get("/logs/stream")
async def stream_logs() -> StreamingResponse:
    """SSE stream of log entries in real time."""
    q = subscribe_logs()

    async def event_generator():
        try:
            while True:
                entry = await q.get()
                yield f"data: {json.dumps(entry)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            unsubscribe_logs(q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
