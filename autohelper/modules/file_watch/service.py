"""File Watch service - manages filesystem watchers per root."""

import logging
from pathlib import Path
from threading import Lock

from watchdog.events import FileSystemEvent

from autohelper.db import get_db
from autohelper.shared.fs_events import get_event_bus

from .handler import FileWatchHandler
from .schemas import FileWatchEvent, WatchRootConfig

logger = logging.getLogger(__name__)


class ThreadSafeEventQueue:
    """Thread-safe queue for file watch events."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._items: list[FileWatchEvent] = []

    def append(self, item: FileWatchEvent) -> None:
        with self._lock:
            self._items.append(item)

    def drain(self) -> list[FileWatchEvent]:
        with self._lock:
            items = self._items[:]
            self._items.clear()
            return items


class FileWatchService:
    """Manages filesystem watchers for root directories."""

    def __init__(self) -> None:
        self._sub_ids: dict[str, str] = {}  # root_id -> bus subscription id
        self._paths: dict[str, str] = {}  # root_id -> resolved path
        self._handlers: dict[str, FileWatchHandler] = {}
        self._event_queues: dict[str, ThreadSafeEventQueue] = {}
        self._lock = Lock()

    def watch(self, root_id: str, path: str) -> bool:
        """
        Start watching a root directory.

        Args:
            root_id: Unique identifier for the root
            path: Filesystem path to watch

        Returns:
            True if watching started successfully, False otherwise
        """
        with self._lock:
            if root_id in self._sub_ids:
                logger.info("Already watching root %s", root_id)
                return True

            root_path = Path(path)
            if not root_path.exists():
                logger.warning("Root path does not exist: %s", root_path)
                return False

            if not root_path.is_dir():
                logger.warning("Root path is not a directory: %s", root_path)
                return False

            # Set up event queue and handler
            event_queue = ThreadSafeEventQueue()
            db = get_db()
            handler = FileWatchHandler(
                root_id=root_id,
                event_queue=event_queue,
                db=db,
            )

            # Subscribe to the shared event bus
            resolved = str(root_path.resolve())
            sub_id = get_event_bus().subscribe(resolved, handler.dispatch)

            self._sub_ids[root_id] = sub_id
            self._paths[root_id] = resolved
            self._handlers[root_id] = handler
            self._event_queues[root_id] = event_queue

            logger.info("Started watching root %s at %s", root_id, root_path)
            return True

    def unwatch(self, root_id: str) -> bool:
        """
        Stop watching a root directory.

        Args:
            root_id: Root identifier to stop watching

        Returns:
            True if watching stopped, False if root was not being watched
        """
        with self._lock:
            sub_id = self._sub_ids.pop(root_id, None)
            self._paths.pop(root_id, None)
            self._handlers.pop(root_id, None)
            self._event_queues.pop(root_id, None)

            if sub_id:
                get_event_bus().unsubscribe(sub_id)
                logger.info("Stopped watching root %s", root_id)
                return True
            return False

    def drain_events(self) -> list[FileWatchEvent]:
        """
        Drain and return all pending events from all watched roots.

        Returns:
            List of file watch events
        """
        with self._lock:
            events: list[FileWatchEvent] = []
            for queue in self._event_queues.values():
                events.extend(queue.drain())
            return events

    def get_watched_roots(self) -> list[WatchRootConfig]:
        """
        Get list of currently watched roots.

        Returns:
            List of watch root configurations
        """
        with self._lock:
            return [
                WatchRootConfig(root_id=root_id, path=self._paths.get(root_id, "<unknown>"))
                for root_id in self._sub_ids
            ]

    def shutdown(self) -> None:
        """Unsubscribe all watchers from the event bus."""
        with self._lock:
            for root_id, sub_id in list(self._sub_ids.items()):
                get_event_bus().unsubscribe(sub_id)
                logger.info("Stopped watching root %s (shutdown)", root_id)
            self._sub_ids.clear()
            self._paths.clear()
            self._handlers.clear()
            self._event_queues.clear()
