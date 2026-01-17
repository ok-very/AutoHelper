"""
Logging configuration with request context support.
"""

import logging
import sys
from contextvars import ContextVar

from .types import RequestContext

# Context variable for request-scoped logging
_request_context: ContextVar[RequestContext | None] = ContextVar("request_context", default=None)


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
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] [%(request_id)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        handler.addFilter(ContextFilter())
        logger.addHandler(handler)
    
    return logger


def get_logger(name: str = "autohelper") -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)
