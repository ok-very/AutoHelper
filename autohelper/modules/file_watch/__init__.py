"""File watch module - detects filesystem changes and matches against references."""

from .router import get_service, router

__all__ = ["router", "get_service"]
