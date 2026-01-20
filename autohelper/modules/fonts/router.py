"""Fonts module routes."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from autohelper.shared.logging import get_logger
from .service import FontService

logger = get_logger(__name__)
router = APIRouter(prefix="/fonts", tags=["fonts"])


@router.get("/{family}/{style}.ttf")
async def get_font(family: str, style: str) -> FileResponse:
    """
    Serve a font file.
    
    Args:
        family: Font family name (e.g., 'Carlito')
        style: Font style (regular, bold, italic, bolditalic)
        
    Returns:
        Font file as binary response
    """
    service = FontService()
    font_path = service.get_font_path(family, style)
    
    if font_path is None:
        raise HTTPException(status_code=404, detail=f"Font not found: {family}/{style}")
    
    return FileResponse(
        path=font_path,
        media_type="font/ttf",
        headers={
            "Cache-Control": "public, max-age=31536000",  # 1 year cache
        }
    )


@router.get("/")
async def list_fonts() -> list[dict]:
    """List all available font families."""
    service = FontService()
    return service.list_fonts()
