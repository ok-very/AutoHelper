"""
Document text extraction for PDF and DOCX files.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_pdf_text(file_path: Path, max_pages: int = 10) -> str | None:
    """
    Extract text from a PDF file.

    Args:
        file_path: Path to PDF file
        max_pages: Maximum pages to extract (for large documents)

    Returns:
        Extracted text or None if extraction fails
    """
    try:
        import pdfplumber
    except ImportError:
        logger.debug("pdfplumber not available, skipping PDF text extraction")
        return None

    try:
        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages[:max_pages]:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

        return "\n\n".join(text_parts) if text_parts else None
    except Exception as e:
        logger.warning(f"PDF text extraction failed for {file_path}: {e}")
        return None


def extract_docx_text(file_path: Path) -> str | None:
    """
    Extract text from a DOCX file.

    Args:
        file_path: Path to DOCX file

    Returns:
        Extracted text or None if extraction fails
    """
    try:
        import docx
    except ImportError:
        logger.debug("python-docx not available, skipping DOCX text extraction")
        return None

    try:
        doc = docx.Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs) if paragraphs else None
    except Exception as e:
        logger.warning(f"DOCX text extraction failed for {file_path}: {e}")
        return None
