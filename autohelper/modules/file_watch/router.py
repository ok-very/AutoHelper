"""File Watch routes."""

from threading import Lock

from fastapi import APIRouter

from .schemas import DrainResponse, WatchRootConfig
from .service import FileWatchService

router = APIRouter(prefix="/file-watch", tags=["file-watch"])

# Module-level singleton (double-checked locking)
_service: FileWatchService | None = None
_service_lock = Lock()


def get_service() -> FileWatchService:
    """Get or create the file watch service singleton."""
    global _service  # noqa: PLW0603
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = FileWatchService()
    return _service


@router.post("/watch")
async def watch_root(config: WatchRootConfig) -> dict[str, bool]:
    """Start watching a root directory for file changes."""
    service = get_service()
    success = service.watch(config.root_id, config.path)
    return {"success": success}


@router.post("/unwatch/{root_id}")
async def unwatch_root(root_id: str) -> dict[str, bool]:
    """Stop watching a root directory."""
    service = get_service()
    success = service.unwatch(root_id)
    return {"success": success}


@router.get("/events")
async def get_events() -> DrainResponse:
    """Drain pending events from all watched roots."""
    service = get_service()
    events = service.drain_events()
    return DrainResponse(events=events, count=len(events))


@router.get("/roots")
async def get_watched_roots() -> dict[str, list[WatchRootConfig]]:
    """Get list of currently watched root directories."""
    service = get_service()
    roots = service.get_watched_roots()
    return {"roots": roots}
