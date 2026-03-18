"""
Filetree module API router.
"""

from fastapi import APIRouter, Query

from .schemas import FiletreeResponse
from .service import FiletreeService

router = APIRouter(prefix="/filetree", tags=["filetree"])


@router.get("", response_model=FiletreeResponse)
async def get_filetree(
    root_id: str | None = Query(None, description="Filter to specific root"),
    max_depth: int = Query(10, ge=1, le=50, description="Maximum tree depth"),
    extensions: str | None = Query(
        None, description="Comma-separated extensions (e.g., '.pdf,.txt')"
    ),
) -> FiletreeResponse:
    """
    Get hierarchical filetree from indexed files.

    Returns a tree structure for each enabled root, filtered by optional parameters.
    """
    service = FiletreeService()

    # Parse extensions
    ext_list: list[str] | None = None
    if extensions:
        ext_list = [e.strip().lower() for e in extensions.split(",") if e.strip()]
        # Ensure extensions start with dot
        ext_list = [e if e.startswith(".") else f".{e}" for e in ext_list]

    roots = service.get_tree(
        root_id=root_id,
        max_depth=max_depth,
        extensions=ext_list,
    )

    return FiletreeResponse(roots=roots)
