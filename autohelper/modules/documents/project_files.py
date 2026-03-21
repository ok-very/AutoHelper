"""
Resolve project metadata from OneDrive project folder structure.

Reads contract documents to extract artwork title and artist details.
Uses document content parsing, not brittle filename conventions.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECTS_ROOT = Path(
    r"C:\Users\silen\OneDrive - Ballard Fine Art"
    r"\BALLARD FINE ART - ALL FILES\1. PUBLIC ART\ALL PROJECTS"
)


@dataclass
class ProjectFileData:
    """Metadata resolved from project folder structure."""
    folder_path: Path | None = None
    folder_name: str = ""
    artist_name: str = ""
    artwork_title: str = ""
    has_contract: bool = False


def find_project_folder(project_name: str, root: Path = PROJECTS_ROOT) -> Path | None:
    """Find the OneDrive project folder by fuzzy matching project name tokens."""
    if not root.is_dir():
        return None
    tokens = project_name.lower().split()
    best: Path | None = None
    best_score = 0
    for folder in root.iterdir():
        if not folder.is_dir():
            continue
        fname = folder.name.lower()
        score = sum(1 for t in tokens if t in fname)
        if score > best_score:
            best = folder
            best_score = score
    return best if best_score > 0 else None


def resolve_project_files(project_name: str, root: Path = PROJECTS_ROOT) -> ProjectFileData:
    """Scan project folder to extract artwork title and artist from contract content."""
    result = ProjectFileData()
    folder = find_project_folder(project_name, root)
    if not folder:
        return result

    result.folder_path = folder
    result.folder_name = folder.name

    # Read the artist contract to extract artwork title and artist name
    ac = folder / "Artist Contract"
    if ac.is_dir():
        result.has_contract = True
        for item in sorted(ac.iterdir()):
            if item.suffix == '.docx' and not item.name.startswith('~') and 'Archive' not in str(item):
                _parse_contract(item, result)
                if result.artwork_title:
                    break

    return result


def _parse_contract(docx_path: Path, result: ProjectFileData) -> None:
    """Extract artwork title and artist name from contract document content.

    Looks for patterns like:
      'install Sacred Belongings (the "Work")'
      'entitled Sacred Belongings to the Owner'
      'AND: Thomas Cannell'
    """
    try:
        from docx import Document
        doc = Document(str(docx_path))
    except Exception as e:
        logger.warning("Could not read contract %s: %s", docx_path.name, e)
        return

    full_text = "\n".join(p.text for p in doc.paragraphs)

    # Extract artwork title — pattern: 'entitled {Title} to' or 'install {Title} (the "Work")'
    for pattern in [
        r'entitled\s+(.+?)\s+to the Owner',
        r'install\s+(.+?)\s*\(the\s*["\u201c]Work["\u201d]\)',
        r'known as\s+(.+?)\s*\(the\s*["\u201c]Work["\u201d]\)',
        r'create.*?(?:titled|entitled|called)\s+(.+?)\s*(?:\(|for)',
    ]:
        m = re.search(pattern, full_text, re.IGNORECASE)
        if m:
            title = m.group(1).strip().strip('""\u201c\u201d')
            if len(title) > 2 and len(title) < 100:
                result.artwork_title = title
                break

    # Extract artist name — pattern: 'AND:\t\tArtist Name' or 'AND: Artist Name'
    for pattern in [
        r'AND:\s+(.+?)$',
        r'\(the\s*["\u201c]Artist["\u201d]\).*?AND:\s+(.+)',
    ]:
        for line in full_text.split('\n'):
            m = re.search(pattern, line.strip())
            if m:
                name = m.group(1).strip()
                # Clean up — remove address lines that might follow
                name = name.split('\n')[0].strip()
                if len(name) > 2 and len(name) < 60 and not name[0].isdigit():
                    result.artist_name = name
                    break
        if result.artist_name:
            break
