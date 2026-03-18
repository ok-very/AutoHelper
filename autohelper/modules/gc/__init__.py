"""Garbage Collection module for automated cleanup."""

from .router import router
from .service import GarbageCollectionService

__all__ = ["router", "GarbageCollectionService"]
