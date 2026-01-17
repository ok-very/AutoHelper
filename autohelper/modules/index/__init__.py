"""Index module - filesystem crawling and indexing."""

from .router import router
from .service import IndexService

__all__ = ["router", "IndexService"]
