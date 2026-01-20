"""Render service - HTML to PDF using Playwright."""

from playwright.async_api import async_playwright

from autohelper.shared.logging import get_logger

logger = get_logger(__name__)


# Page presets matching @autoart/shared PDF_PAGE_PRESETS
# Dimensions in pixels at 96 DPI
PAGE_PRESETS = {
    "letter": {"width": 816, "height": 1056, "format": "Letter"},
    "legal": {"width": 816, "height": 1344, "format": "Legal"},
    "tabloid": {"width": 1056, "height": 1632, "format": "Tabloid"},
    "tearsheet": {"width": 1344, "height": 816, "format": "Tabloid", "landscape": True},
    "a4": {"width": 794, "height": 1123, "format": "A4"},
}

DEFAULT_MARGINS = {
    "top": "0.5in",
    "bottom": "0.5in",
    "left": "0.5in",
    "right": "0.5in",
}


class RenderService:
    """Service for rendering HTML to PDF using Playwright."""
    
    async def html_to_pdf(
        self,
        html: str,
        page_preset: str = "letter",
        margins: dict[str, str] | None = None,
        print_background: bool = True,
    ) -> bytes:
        """
        Render HTML content to PDF bytes.
        
        Args:
            html: HTML content to render
            page_preset: Page size preset (letter, legal, tabloid, tearsheet, a4)
            margins: Custom margins (top, bottom, left, right in CSS units)
            print_background: Include background colors and images
            
        Returns:
            PDF bytes
        """
        preset = PAGE_PRESETS.get(page_preset, PAGE_PRESETS["letter"])
        effective_margins = margins or DEFAULT_MARGINS
        
        logger.info(f"Rendering PDF with preset '{page_preset}': {preset['width']}x{preset['height']}px")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            
            try:
                page = await browser.new_page()
                
                # Set viewport to match page dimensions
                await page.set_viewport_size({
                    "width": preset["width"],
                    "height": preset["height"]
                })
                
                # Load HTML content
                await page.set_content(html, wait_until="networkidle")
                
                # Generate PDF
                pdf_options = {
                    "format": preset["format"],
                    "margin": effective_margins,
                    "print_background": print_background,
                    "prefer_css_page_size": True,
                }
                
                # Handle landscape mode
                if preset.get("landscape"):
                    pdf_options["landscape"] = True
                
                pdf_bytes = await page.pdf(**pdf_options)
                
                logger.info(f"Generated PDF: {len(pdf_bytes)} bytes")
                return pdf_bytes
                
            finally:
                await browser.close()
