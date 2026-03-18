"""Filesystem event handler for file watching."""

import logging
import time
from collections import defaultdict
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING

from autohelper.db.conn import Database

from watchdog.events import (
    DirCreatedEvent,
    DirDeletedEvent,
    DirMovedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileMovedEvent,
    FileSystemEvent,
    FileSystemEventHandler,
    EVENT_TYPE_CREATED,
    EVENT_TYPE_DELETED,
    EVENT_TYPE_MOVED,
)

from .schemas import FileEventType, FileWatchEvent

if TYPE_CHECKING:
    from .service import ThreadSafeEventQueue

logger = logging.getLogger(__name__)


class FileWatchHandler(FileSystemEventHandler):
    """Handles filesystem events and matches against reference registry."""

    def __init__(
        self,
        root_id: str,
        event_queue: "ThreadSafeEventQueue",
        db: Database,
        debounce_window: float = 0.5,
    ) -> None:
        """
        Initialize the file watch handler.

        Args:
            root_id: Root directory identifier
            event_queue: Thread-safe queue to append events to
            db: Database wrapper for ref lookups
            debounce_window: Seconds to wait before emitting event for same path
        """
        super().__init__()
        self.root_id = root_id
        self.event_queue = event_queue
        self.db = db
        self.debounce_window = debounce_window
        self._lock = Lock()
        self._last_event_time: dict[str, float] = defaultdict(float)

    def on_created(self, event: FileCreatedEvent | DirCreatedEvent) -> None:
        """Handle file creation events."""
        if event.is_directory:
            return

        path = Path(str(event.src_path))
        if not self._should_emit(str(path)):
            return

        canonical_path = str(path.resolve())
        ref_id = self._lookup_ref(canonical_path)

        file_event = FileWatchEvent(
            event_type=FileEventType.CREATED,
            path=canonical_path,
            ref_id=ref_id,
            root_id=self.root_id,
        )

        self.event_queue.append(file_event)

        logger.info(
            "File watch: created %s (ref_id=%s)",
            path.name,
            ref_id or "none",
        )

    def on_deleted(self, event: FileDeletedEvent | DirDeletedEvent) -> None:
        """Handle file deletion events."""
        if event.is_directory:
            return

        path = Path(str(event.src_path))
        if not self._should_emit(str(path)):
            return

        # Use absolute() instead of resolve() — file is already gone, resolve() can raise
        canonical_path = str(path.absolute())
        ref_id = self._lookup_ref(canonical_path)

        file_event = FileWatchEvent(
            event_type=FileEventType.DELETED,
            path=canonical_path,
            ref_id=ref_id,
            root_id=self.root_id,
        )

        self.event_queue.append(file_event)

        logger.info(
            "File watch: deleted %s (ref_id=%s)",
            path.name,
            ref_id or "none",
        )

    def on_moved(self, event: FileMovedEvent | DirMovedEvent) -> None:
        """Handle file move events."""
        if event.is_directory:
            return

        src_path = Path(str(event.src_path))
        dest_path = Path(str(event.dest_path))

        if not self._should_emit(str(dest_path)):
            return

        src_canonical = str(src_path.resolve())
        dest_canonical = str(dest_path.resolve())

        # Check both paths for refs
        ref_id = self._lookup_ref(dest_canonical) or self._lookup_ref(src_canonical)

        file_event = FileWatchEvent(
            event_type=FileEventType.MOVED,
            path=dest_canonical,
            old_path=src_canonical,
            ref_id=ref_id,
            root_id=self.root_id,
        )

        self.event_queue.append(file_event)

        logger.info(
            "File watch: moved %s -> %s (ref_id=%s)",
            src_path.name,
            dest_path.name,
            ref_id or "none",
        )

    def dispatch(self, event: FileSystemEvent) -> None:
        """Route a raw watchdog event to the appropriate on_* method.

        Called by FsEventBus instead of watchdog's internal dispatch.
        """
        if event.event_type == EVENT_TYPE_CREATED:
            self.on_created(event)
        elif event.event_type == EVENT_TYPE_DELETED:
            self.on_deleted(event)
        elif event.event_type == EVENT_TYPE_MOVED:
            self.on_moved(event)
        # modified / closed events are intentionally ignored

    def _should_emit(self, path: str) -> bool:
        """Check if we should emit an event for this path (debounce rapid events)."""
        now = time.time()
        with self._lock:
            last_time = self._last_event_time[path]
            if now - last_time < self.debounce_window:
                logger.debug("Debounced event for %s", path)
                return False
            self._last_event_time[path] = now
            return True

    def _lookup_ref(self, canonical_path: str) -> str | None:
        """Look up ref_id for a given canonical path."""
        try:
            cursor = self.db.execute(
                "SELECT ref_id FROM refs WHERE canonical_path = ?",
                (canonical_path,),
            )
            row = cursor.fetchone()
            return row[0] if row else None
        except Exception:
            logger.exception("Failed to lookup ref for path: %s", canonical_path)
            return None
