"""
Utility functions: name normalization, date parsing, file classification,
concept-proposal parsing, text extraction.

Ported from BFA-artist-lists/scripts/utils.py with generalisations.
"""
from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path

from .config import get_lexicon


# ---------------------------------------------------------------------------
# Name normalisation
# ---------------------------------------------------------------------------

def normalize_name(raw: str) -> str:
    """Lower-case, remove accents, replace non-alnum with underscore, collapse."""
    s = unicodedata.normalize("NFKD", raw)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9]+", "_", s.lower())
    s = s.strip("_")
    return s


def generate_artist_id(folder_name: str) -> str:
    """Derive a canonical artist_id from a folder name."""
    lex = get_lexicon()
    fixed = lex.folder_name_fixes.get(folder_name, folder_name)
    return normalize_name(fixed)


def parse_display_name(folder_name: str) -> tuple[str, str | None, str | None]:
    """
    Parse folder name into (display_name, first_name, last_name).

    Returns display_name as "First Last" convention where possible.
    """
    lex = get_lexicon()
    fixed = lex.folder_name_fixes.get(folder_name, folder_name)

    if "," in fixed:
        parts = fixed.split(",", 1)
        last = parts[0].strip()
        first = parts[1].strip()
        display = f"{first} {last}"
        return display, first, last
    else:
        tokens = fixed.split()
        if len(tokens) == 1:
            return fixed, None, fixed
        elif len(tokens) == 2:
            return fixed, tokens[0], tokens[1]
        else:
            return fixed, tokens[0], " ".join(tokens[1:])


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

_DATE_PATTERNS = [
    (re.compile(r"(\d{4})[_\-](\d{2})[_\-](\d{2})"), "{0}-{1}-{2}"),
    (re.compile(r"(\d{4})[_\-](\d{2})"), "{0}-{1}"),
    (re.compile(r"(\d{4})"), "{0}"),
]


def parse_date_from_filename(filename: str) -> str | None:
    """Extract the earliest/most specific date from a filename."""
    stem = os.path.splitext(filename)[0]
    for pattern, fmt in _DATE_PATTERNS:
        m = pattern.search(stem)
        if m:
            return fmt.format(*m.groups())
    return None


# ---------------------------------------------------------------------------
# File classification
# ---------------------------------------------------------------------------

def classify_file(filename: str) -> str:
    """
    Return one of: 'image', 'bio', 'cv', 'tearsheet', 'project_list',
    'url', 'document', 'ignore', 'other'.
    """
    lex = get_lexicon()
    lower = filename.lower()
    if lower in lex.ignore_files or lower.startswith("."):
        return "ignore"

    ext = os.path.splitext(lower)[1]

    if ext == ".url":
        return "url"

    if ext in lex.image_extensions:
        return "image"

    # Document classification by keyword
    if "tearsheet" in lower:
        return "tearsheet"
    if "_bio" in lower or lower.endswith("_bio") or lower.startswith("bio"):
        return "bio"
    if "_cv" in lower or lower.endswith("_cv") or lower.startswith("cv"):
        return "cv"
    if "curriculum vitae" in lower:
        return "cv"
    if "project" in lower and "list" in lower:
        return "project_list"
    if "project" in lower:
        return "project_list"

    if ext in lex.document_extensions:
        return "document"

    return "other"


def normalise_subfolder(name: str) -> str:
    """Normalise a subfolder name using the lexicon's aliases."""
    lex = get_lexicon()
    return lex.subfolder_aliases.get(name.lower(), name)


# ---------------------------------------------------------------------------
# URL file reading
# ---------------------------------------------------------------------------

def read_url_file(path: str) -> str | None:
    """Read a Windows .url shortcut and return the URL string."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if line.upper().startswith("URL="):
                    return line[4:].strip()
    except OSError:
        pass
    return None


# ---------------------------------------------------------------------------
# Concept proposal / EOI name parsing
# ---------------------------------------------------------------------------

_PROPOSAL_FOLDER_PATTERN = re.compile(
    r"^(\d{4}[_\-]\d{2}(?:[_\-]\d{2})?)[_\-](.+)$"
)


def parse_concept_proposal_folder(folder_name: str) -> dict:
    """Parse a concept-proposal folder name into {date, developer, project_name}."""
    m = _PROPOSAL_FOLDER_PATTERN.match(folder_name)
    if not m:
        return {"date": None, "developer": None, "project_name": folder_name}

    raw_date = m.group(1).replace("_", "-")
    rest = m.group(2)
    parts = rest.split("_")
    first_part = parts[0]
    hyphen_parts = first_part.split("-", 1)
    developer = _camel_to_words(hyphen_parts[0])
    project_name = _camel_to_words(hyphen_parts[1]) if len(hyphen_parts) > 1 else ""

    return {
        "date": raw_date,
        "developer": developer.strip() or None,
        "project_name": project_name.strip() or None,
    }


def parse_concept_proposal_file(filename: str) -> dict:
    """Parse a concept-proposal filename into {date, developer, project_name}."""
    stem = os.path.splitext(filename)[0]
    m = _PROPOSAL_FOLDER_PATTERN.match(stem)
    if not m:
        return {"date": None, "developer": None, "project_name": stem}

    raw_date = m.group(1).replace("_", "-")
    rest = m.group(2)
    parts = rest.split("_")
    first_part = parts[0]
    hyphen_parts = first_part.split("-", 1)
    developer = _camel_to_words(hyphen_parts[0])
    project_name = _camel_to_words(hyphen_parts[1]) if len(hyphen_parts) > 1 else ""

    return {
        "date": raw_date,
        "developer": developer.strip() or None,
        "project_name": project_name.strip() or None,
    }


def parse_eoi_folder(folder_name: str) -> str | None:
    """Extract project name from an EOI folder name."""
    name = re.sub(r"^[A-Za-z\s,.]+ - ", "", folder_name)
    name = re.sub(r"\s+(EOI|Submission|RFP|RFQ)$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"^\d{4}[_\-]\d{2}[_\-]\d{2}[_\-]?\s*", "", name)
    name = name.strip()
    return name if name else folder_name


def _camel_to_words(s: str) -> str:
    """Insert space before capital runs: 'PCUrban' -> 'PC Urban'."""
    return re.sub(r"([a-z])([A-Z])", r"\1 \2", s)


# ---------------------------------------------------------------------------
# Tearsheet "is current" logic
# ---------------------------------------------------------------------------

def is_current_tearsheet(file_path: str, tearsheet_root: str) -> bool:
    """A tearsheet is current if it is NOT inside an 'Old' subfolder."""
    rel = os.path.relpath(file_path, tearsheet_root)
    parts = rel.split(os.sep)
    return not any(p.lower() == "old" for p in parts)


# ---------------------------------------------------------------------------
# Text extraction (for inline bio display)
# ---------------------------------------------------------------------------

def extract_text(file_path: str, max_chars: int = 10_000) -> str | None:
    """
    Extract plain text from a document file.

    Supports: .txt, .docx, .pdf, .rtf
    Returns None on failure or unsupported format.
    """
    ext = os.path.splitext(file_path)[1].lower()
    try:
        if ext == ".txt":
            return _read_txt(file_path, max_chars)
        elif ext == ".docx":
            return _read_docx(file_path, max_chars)
        elif ext == ".pdf":
            return _read_pdf(file_path, max_chars)
        elif ext == ".rtf":
            return _read_rtf(file_path, max_chars)
    except Exception:
        pass
    return None


def _read_txt(path: str, max_chars: int) -> str | None:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read(max_chars)
    return text.strip() or None


def _read_docx(path: str, max_chars: int) -> str | None:
    from docx import Document

    doc = Document(path)
    paragraphs = []
    total = 0
    for para in doc.paragraphs:
        paragraphs.append(para.text)
        total += len(para.text)
        if total > max_chars:
            break
    text = "\n".join(paragraphs)
    return text[:max_chars].strip() or None


def _read_pdf(path: str, max_chars: int) -> str | None:
    import pdfplumber

    text_parts = []
    total = 0
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)
            total += len(page_text)
            if total > max_chars:
                break
    text = "\n".join(text_parts)
    return text[:max_chars].strip() or None


def _read_rtf(path: str, max_chars: int) -> str | None:
    from striprtf.striprtf import rtf_to_text

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        rtf_content = f.read(max_chars * 3)  # RTF markup inflates text
    text = rtf_to_text(rtf_content)
    return text[:max_chars].strip() or None
