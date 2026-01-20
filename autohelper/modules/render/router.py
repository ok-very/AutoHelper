"""Render module routes."""

from fastapi import APIRouter, Response

from autohelper.shared.logging import get_logger
from .schemas import RenderPdfRequest
from .service import RenderService

logger = get_logger(__name__)
router = APIRouter(prefix="/render", tags=["render"])


@router.post("/pdf")
async def render_pdf(request: RenderPdfRequest) -> Response:
    """
    Render HTML to PDF using Playwright.
    
    Returns the PDF as binary content with appropriate headers.
    """
    service = RenderService()
    
    try:
        pdf_bytes = await service.html_to_pdf(
            html=request.html,
            page_preset=request.page_preset,
            margins=request.margins,
            print_background=request.print_background,
        )
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=export.pdf",
                "Content-Length": str(len(pdf_bytes)),
            }
        )
        
    except Exception as e:
        logger.error(f"PDF render failed: {e}")
        return Response(
            content=f"PDF rendering failed: {str(e)}",
            status_code=500,
            media_type="text/plain"
        )
