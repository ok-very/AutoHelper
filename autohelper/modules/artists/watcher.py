"""
Artist file watcher — monitors the storage root for changes and triggers
per-artist rescans with debouncing.

Subscribes to the shared FsEventBus so that only one watchdog Observer runs
per unique path, even when the file_watch module monitors the same tree.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEvent

logger = logging.getLogger(__name__)

DEBOUNCE_SECONDS = 5.0


class ArtistFileWatcher:
    """Watches the artist storage root and triggers per-artist rescans."""

    def __init__(self) -> None:
        self._sub_id: str | None = None
        self._flush_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._pending_folders: dict[str, float] = {}  # folder_path -> last_event_time
        self._get_db: Any = None

    def start(self, storage_root: str) -> bool:
        """Start watching the storage root. Returns True on success."""
        root = Path(storage_root)
        if not root.is_dir():
            logger.warning("Artist storage root not found: %s", root)
            return False

        if self._sub_id is not None:
            self.stop()

        from autohelper.db import get_db
        from autohelper.shared.fs_events import get_event_bus

        self._get_db = get_db

        self._sub_id = get_event_bus().subscribe(str(root), self._on_event)

        self._stop_event.clear()
        self._flush_thread = threading.Thread(
            target=self._flush_loop, daemon=True, name="artist-watcher-flush"
        )
        self._flush_thread.start()

        logger.info("Artist watcher started on %s", root)
        return True

    def stop(self) -> None:
        """Stop the watcher and flush thread."""
        self._stop_event.set()

        if self._sub_id is not None:
            from autohelper.shared.fs_events import get_event_bus

            get_event_bus().unsubscribe(self._sub_id)
            self._sub_id = None

        if self._flush_thread is not None:
            self._flush_thread.join(timeout=10)
            self._flush_thread = None

        logger.info("Artist watcher stopped")

    # -- event handling ------------------------------------------------------

    def _on_event(self, event: FileSystemEvent) -> None:
        """Called on watchdog's thread for every filesystem event."""
        if event.is_directory:
            return

        src = event.src_path
        if not src:
            return

        # Ignore hidden files and system files
        basename = os.path.basename(src).lower()
        if basename.startswith(".") or basename in (
            "thumbs.db", "desktop.ini", ".ds_store",
        ):
            return

        folder = self._find_artist_folder(src)
        if folder:
            with self._lock:
                self._pending_folders[folder] = time.monotonic()

    def _find_artist_folder(self, file_path: str) -> str | None:
        """Walk up from file_path looking for a registered artist folder."""
        if self._get_db is None:
            return None
        try:
            db = self._get_db()
        except Exception:
            return None

        current = os.path.dirname(file_path)
        checked: set[str] = set()

        while current and current not in checked:
            checked.add(current)
            row = db.execute(
                "SELECT folder_path FROM artist_folders WHERE folder_path = ?",
                (current,),
            ).fetchone()
            if row:
                return row[0]
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent

        return None

    # -- flush loop ----------------------------------------------------------

    def _flush_loop(self) -> None:
        """Periodically flush pending artist rescans."""
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=DEBOUNCE_SECONDS)
            if self._stop_event.is_set():
                break
            self._flush_pending()

    def _flush_pending(self) -> None:
        """Rescan all pending artist folders that have been quiet for DEBOUNCE_SECONDS."""
        with self._lock:
            now = time.monotonic()
            ready = {
                folder: ts
                for folder, ts in self._pending_folders.items()
                if now - ts >= DEBOUNCE_SECONDS
            }
            for folder in ready:
                del self._pending_folders[folder]

        if not ready:
            return

        from .service import get_artist_service

        svc = get_artist_service()

        for folder_path in ready:
            try:
                result = svc.rescan_folder(folder_path)
                logger.info(
                    "Watcher rescan for %s: %s",
                    os.path.basename(folder_path),
                    result.get("status", result.get("error", "?")),
                )
            except Exception:
                logger.error("Watcher rescan failed for %s", folder_path, exc_info=True)


# Singleton
_watcher: ArtistFileWatcher | None = None


def get_artist_watcher() -> ArtistFileWatcher:
    global _watcher
    if _watcher is None:
        _watcher = ArtistFileWatcher()
    return _watcher
