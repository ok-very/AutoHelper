"""
Search module API router.
"""

from fastapi import APIRouter, Query

from .schemas import SearchResponse
from .service import SearchService

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1, description="Search query"), limit: int = 50
) -> SearchResponse:
    """
    Search for files.
    """
    service = SearchService()
    return service.search(query=q, limit=limit)
