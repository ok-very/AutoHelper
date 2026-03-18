"""FastAPI router for Felt interactive map operations."""

from fastapi import APIRouter, HTTPException

from .service import create_context_map, validate_connection
from autohelper.modules.documents.context_map.types import ContextMapRequest, ContextMapResult

router = APIRouter(prefix="/felt", tags=["felt"])


@router.post("/context-map", response_model=ContextMapResult)
async def post_context_map(request: ContextMapRequest) -> ContextMapResult:
    """Create an interactive Felt context map for a project site."""
    try:
        return await create_context_map(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/validate")
async def get_validate() -> dict:
    """Test the Felt API token and return workspace info."""
    try:
        info = await validate_connection()
        return {"status": "ok", "user": info}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Felt API error: {e}") from e
