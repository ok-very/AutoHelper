"""Invoice Watch routes."""

from typing import Any

from fastapi import APIRouter

from .schemas import (
    ValidateNumberRequest,
    ValidateNumberResponse,
    WatchProjectCommand,
)
from .service import InvoiceWatchService

router = APIRouter(prefix="/invoice-watch", tags=["invoice-watch"])

# Module-level singleton
_service: InvoiceWatchService | None = None


def get_service() -> InvoiceWatchService:
    """Get or create the invoice watch service singleton."""
    global _service  # noqa: PLW0603
    if _service is None:
        _service = InvoiceWatchService()
    return _service


@router.post("/watch")
async def watch_project(command: WatchProjectCommand) -> dict[str, bool]:
    """Start watching a project folder for invoice artifacts."""
    service = get_service()
    success = service.watch_project(command)
    return {"success": success}


@router.post("/unwatch")
async def unwatch_project(project_id: str) -> dict[str, bool]:
    """Stop watching a project folder."""
    service = get_service()
    success = service.unwatch_project(project_id)
    return {"success": success}


@router.get("/events")
async def get_events(project_id: str | None = None) -> dict[str, list[dict[str, Any]]]:
    """Drain pending events from the watch queue."""
    service = get_service()
    events = service.drain_events(project_id)
    return {"events": [e.model_dump(mode="json") for e in events]}


@router.get("/projects")
async def get_watched_projects() -> dict[str, list[str]]:
    """Get list of currently watched project IDs."""
    service = get_service()
    return {"projects": service.get_watched_projects()}


@router.get("/validate-number")
async def validate_number(number: str, project_root: str) -> ValidateNumberResponse:
    """Validate an invoice number against files on disk."""
    service = get_service()
    return service.validate_number(
        ValidateNumberRequest(number=number, project_root=project_root)
    )
