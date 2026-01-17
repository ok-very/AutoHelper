"""
Index module internal types.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

@dataclass
class ScanResult:
    """Result of a scan operation."""
    added: int = 0
    updated: int = 0
    removed: int = 0
    errors: int = 0
    total_size: int = 0
    duration_ms: int = 0

@dataclass
class FileEntry:
    """Internal representation of a file to be indexed."""
    path: Path
    root_id: str
    stat: Any  # FileStat
    content_hash: str | None = None
