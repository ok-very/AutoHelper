"""Shared filesystem event bus — single watchdog Observer per unique path."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


@dataclass
class _Subscription:
    sub_id: str
    path: str  # resolved path this subscription is under
    callback: Callable[[FileSystemEvent], None]


@dataclass
class _PathState:
    """Tracks the Observer and subscriptions for a single watched path."""
    observer: Observer
    handler: _DispatchHandler
    sub_ids: list[str] = field(default_factory=list)


class _DispatchHandler(FileSystemEventHandler):
    """Forwards every event to all registered callbacks for this path."""

    def __init__(self, bus: FsEventBus, path: str) -> None:
        super().__init__()
        self._bus = bus
        self._path = path

    def on_any_event(self, event: FileSystemEvent) -> None:
        self._bus._dispatch(self._path, event)


class FsEventBus:
    """Single watchdog Observer per unique path, dispatches to registered consumers."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._paths: dict[str, _PathState] = {}  # resolved path -> state
        self._subs: dict[str, _Subscription] = {}  # sub_id -> subscription

    def subscribe(self, path: str, callback: Callable[[FileSystemEvent], None]) -> str:
        """Register a callback for events under *path*. Returns subscription ID."""
        resolved = str(Path(path).resolve())
        sub_id = uuid.uuid4().hex

        with self._lock:
            sub = _Subscription(sub_id=sub_id, path=resolved, callback=callback)
            self._subs[sub_id] = sub

            state = self._paths.get(resolved)
            if state is None:
                state = self._start_observer(resolved)
            state.sub_ids.append(sub_id)

        logger.info(
            "FsEventBus: subscribed %s under %s (%d total subs for path)",
            sub_id[:8],
            resolved,
            len(state.sub_ids),
        )
        return sub_id

    def unsubscribe(self, sub_id: str) -> None:
        """Remove a subscription. Stops Observer when last sub for a path leaves."""
        with self._lock:
            sub = self._subs.pop(sub_id, None)
            if sub is None:
                return

            state = self._paths.get(sub.path)
            if state is None:
                return

            if sub_id in state.sub_ids:
                state.sub_ids.remove(sub_id)

            if not state.sub_ids:
                self._stop_observer(sub.path, state)

        logger.info("FsEventBus: unsubscribed %s", sub_id[:8])

    def shutdown(self) -> None:
        """Stop all observers."""
        with self._lock:
            for path, state in list(self._paths.items()):
                self._stop_observer(path, state)
            self._subs.clear()
        logger.info("FsEventBus: shutdown complete")

    # -- internal ------------------------------------------------------------

    def _start_observer(self, resolved_path: str) -> _PathState:
        """Start a new Observer for *resolved_path*. Caller holds the lock."""
        handler = _DispatchHandler(self, resolved_path)
        observer = Observer()
        observer.schedule(handler, resolved_path, recursive=True)
        observer.start()
        state = _PathState(observer=observer, handler=handler)
        self._paths[resolved_path] = state
        logger.info("FsEventBus: started Observer on %s", resolved_path)
        return state

    def _stop_observer(self, resolved_path: str, state: _PathState) -> None:
        """Stop and remove the Observer for *resolved_path*. Caller holds the lock."""
        state.observer.stop()
        state.observer.join(timeout=5)
        self._paths.pop(resolved_path, None)
        logger.info("FsEventBus: stopped Observer on %s", resolved_path)

    def _dispatch(self, path: str, event: FileSystemEvent) -> None:
        """Called on watchdog's thread — fan-out to matching callbacks."""
        with self._lock:
            state = self._paths.get(path)
            if state is None:
                return
            # Snapshot the callbacks to release lock before calling
            callbacks = [
                self._subs[sid].callback
                for sid in state.sub_ids
                if sid in self._subs
            ]

        for cb in callbacks:
            try:
                cb(event)
            except Exception:
                logger.exception("FsEventBus: callback error for event %s", event)


# Singleton ----------------------------------------------------------------

_bus: FsEventBus | None = None
_bus_lock = Lock()


def get_event_bus() -> FsEventBus:
    global _bus
    if _bus is None:
        with _bus_lock:
            if _bus is None:
                _bus = FsEventBus()
    return _bus
