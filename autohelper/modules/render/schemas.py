"""Render module schemas."""

from pydantic import BaseModel, Field


class RenderPdfRequest(BaseModel):
    """Request to render HTML to PDF."""
    
    html: str = Field(..., description="HTML content to render")
    page_preset: str = Field(
        default="letter",
        description="Page preset: letter, legal, tabloid, tearsheet, a4"
    )
    margins: dict[str, str] | None = Field(
        default=None,
        description="Custom margins (top, bottom, left, right in CSS units)"
    )
    print_background: bool = Field(
        default=True,
        description="Include background colors and images"
    )


class RenderPdfResponse(BaseModel):
    """Response containing PDF metadata (actual bytes returned as binary)."""
    
    success: bool
    size_bytes: int | None = None
    error: str | None = None
