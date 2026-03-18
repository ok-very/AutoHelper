"""Invoice Watch service - manages filesystem watchers per project."""

import logging
from pathlib import Path
from threading import Lock
from typing import Any

from watchdog.observers import Observer as WatchdogObserver

from .handlers import InvoiceWatchHandler
from .schemas import (
    FileEvent,
    ValidateNumberRequest,
    ValidateNumberResponse,
    WatchedFolder,
    WatchProjectCommand,
)

logger = logging.getLogger(__name__)


class InvoiceWatchService:
    """Manages filesystem watchers for project invoice directories."""

    def __init__(self) -> None:
        self._observers: dict[str, Any] = {}  # project_id -> Observer
        self._handlers: dict[str, InvoiceWatchHandler] = {}
        self._event_queues: dict[str, list[FileEvent]] = {}
        self._lock = Lock()

    def watch_project(self, command: WatchProjectCommand) -> bool:
        """Start watching a project's directories."""
        with self._lock:
            if command.project_id in self._observers:
                logger.info("Already watching project %s", command.project_id)
                return True

            root = Path(command.root_path)
            if not root.exists():
                logger.warning("Project root does not exist: %s", root)
                return False

            # Ensure expected subdirectories exist
            for folder_name in command.folders:
                folder_path = root / folder_name
                folder_path.mkdir(parents=True, exist_ok=True)

            # Set up event queue and handler
            event_queue: list[FileEvent] = []
            handler = InvoiceWatchHandler(
                project_id=command.project_id,
                project_root=root,
                event_queue=event_queue,
            )

            # Create and start observer
            observer = WatchdogObserver()
            observer.schedule(handler, str(root), recursive=True)
            observer.start()

            self._observers[command.project_id] = observer
            self._handlers[command.project_id] = handler
            self._event_queues[command.project_id] = event_queue

            logger.info("Started watching project %s at %s", command.project_id, root)
            return True

    def unwatch_project(self, project_id: str) -> bool:
        """Stop watching a project's directories."""
        with self._lock:
            observer = self._observers.pop(project_id, None)
            self._handlers.pop(project_id, None)
            self._event_queues.pop(project_id, None)

            if observer:
                observer.stop()
                observer.join(timeout=5)
                logger.info("Stopped watching project %s", project_id)
                return True
            return False

    def drain_events(self, project_id: str | None = None) -> list[FileEvent]:
        """Drain and return pending events, optionally for a specific project."""
        with self._lock:
            events: list[FileEvent] = []
            if project_id:
                queue = self._event_queues.get(project_id, [])
                events.extend(queue)
                queue.clear()
            else:
                for queue in self._event_queues.values():
                    events.extend(queue)
                    queue.clear()
            return events

    def get_watched_projects(self) -> list[str]:
        """Return list of currently watched project IDs."""
        with self._lock:
            return list(self._observers.keys())

    def validate_number(self, request: ValidateNumberRequest) -> ValidateNumberResponse:
        """Check if an invoice number exists on disk in the project's invoices folder."""
        invoices_dir = Path(request.project_root) / WatchedFolder.INVOICES.value
        matching_files: list[str] = []

        if invoices_dir.exists():
            normalized = request.number.upper().replace("_", "-")
            for file_path in invoices_dir.iterdir():
                if file_path.is_file() and normalized in file_path.name.upper():
                    matching_files.append(str(file_path))

        return ValidateNumberResponse(
            exists_on_disk=len(matching_files) > 0,
            matching_files=matching_files,
        )

    def shutdown(self) -> None:
        """Stop all observers."""
        with self._lock:
            for project_id, observer in list(self._observers.items()):
                observer.stop()
                observer.join(timeout=5)
                logger.info("Stopped watching project %s (shutdown)", project_id)
            self._observers.clear()
            self._handlers.clear()
            self._event_queues.clear()
