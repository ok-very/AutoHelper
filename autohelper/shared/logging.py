"""
Logging configuration with request context support.

Includes a ring-buffer handler that retains recent log entries and an SSE
generator so the dashboard can stream logs in real time.
"""

import asyncio
import logging
import sys
import time
from collections import deque
from contextvars import ContextVar

from .types import RequestContext

# Context variable for request-scoped logging
_request_context: ContextVar[RequestContext | None] = ContextVar("request_context", default=None)

# ── Ring-buffer log handler ────────────────────────────────────────

MAX_LOG_ENTRIES = 500

_log_buffer: deque[dict] = deque(maxlen=MAX_LOG_ENTRIES)
_log_subscribers: list[asyncio.Queue] = []


class BufferHandler(logging.Handler):
    """Append formatted log records to an in-memory ring buffer and notify SSE subscribers."""

    def emit(self, record: logging.LogRecord) -> None:
        entry = {
            "ts": record.created,
            "level": record.levelname,
            "name": record.name.replace("autohelper.", ""),
            "msg": self.format(record),
        }
        _log_buffer.append(entry)
        for q in list(_log_subscribers):
            try:
                q.put_nowait(entry)
            except asyncio.QueueFull:
                pass


def get_log_buffer() -> list[dict]:
    """Return a snapshot of recent log entries."""
    return list(_log_buffer)


def subscribe_logs() -> asyncio.Queue:
    """Create a new SSE subscriber queue."""
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _log_subscribers.append(q)
    return q


def unsubscribe_logs(q: asyncio.Queue) -> None:
    """Remove an SSE subscriber queue."""
    try:
        _log_subscribers.remove(q)
    except ValueError:
        pass


def get_request_context() -> RequestContext | None:
    """Get the current request context."""
    return _request_context.get()


def set_request_context(ctx: RequestContext) -> None:
    """Set the current request context."""
    _request_context.set(ctx)


def clear_request_context() -> None:
    """Clear the current request context."""
    _request_context.set(None)


class ContextFilter(logging.Filter):
    """Add request context to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        ctx = get_request_context()
        if ctx:
            record.request_id = ctx.request_id
            record.work_item_id = ctx.work_item_id or "-"
            record.context_id = ctx.context_id or "-"
        else:
            record.request_id = "-"
            record.work_item_id = "-"
            record.context_id = "-"
        return True


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure application logging."""
    logger = logging.getLogger("autohelper")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if not logger.handlers:
        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] [%(request_id)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        handler.addFilter(ContextFilter())
        logger.addHandler(handler)

        # Ring-buffer handler for dashboard console
        buf_handler = BufferHandler()
        buf_handler.setFormatter(fmt)
        logger.addHandler(buf_handler)

    return logger


def get_logger(name: str = "autohelper") -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)
