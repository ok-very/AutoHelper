"""
Content extractors submodule.

Provides HTML content extraction functions decoupled from HTTP fetching.
"""

from .bio import extract_bio_text
from .contact import extract_emails, extract_location, extract_phones
from .documents import extract_cv_links, extract_pdf_links
from .images import SUPPORTED_IMAGE_EXTENSIONS, extract_image_urls
from .text import extract_docx_text, extract_pdf_text

__all__ = [
    # Bio extraction
    "extract_bio_text",
    # Image extraction
    "extract_image_urls",
    "SUPPORTED_IMAGE_EXTENSIONS",
    # Contact extraction
    "extract_emails",
    "extract_phones",
    "extract_location",
    # Document extraction
    "extract_cv_links",
    "extract_pdf_links",
    # Text extraction
    "extract_pdf_text",
    "extract_docx_text",
]
