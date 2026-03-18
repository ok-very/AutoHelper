"""
Filesystem protocols for testability.
Allows mocking filesystem operations in tests.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass
class FileStat:
    """File stat information."""

    path: Path
    size: int
    mtime_ns: int
    is_dir: bool
    is_symlink: bool
    is_offline: bool = False  # OneDrive Files On-Demand: True if file is cloud-only

    @property
    def mtime(self) -> datetime:
        """Convert mtime_ns to datetime."""
        return datetime.fromtimestamp(self.mtime_ns / 1_000_000_000)


@runtime_checkable
class FileSystem(Protocol):
    """Protocol for filesystem operations."""

    def stat(self, path: Path) -> FileStat:
        """Get file stat info."""
        ...

    def exists(self, path: Path) -> bool:
        """Check if path exists."""
        ...

    def is_dir(self, path: Path) -> bool:
        """Check if path is a directory."""
        ...

    def is_file(self, path: Path) -> bool:
        """Check if path is a file."""
        ...

    def is_symlink(self, path: Path) -> bool:
        """Check if path is a symlink."""
        ...

    def read_bytes(self, path: Path) -> bytes:
        """Read file contents as bytes."""
        ...

    def read_text(self, path: Path, encoding: str = "utf-8") -> str:
        """Read file contents as text."""
        ...

    def iterdir(self, path: Path) -> list[Path]:
        """List directory contents."""
        ...

    def walk(self, path: Path) -> list[tuple[Path, list[str], list[str]]]:
        """Walk directory tree."""
        ...


@runtime_checkable
class Hasher(Protocol):
    """Protocol for content hashing."""

    def hash_file(self, path: Path, max_size: int | None = None) -> str | None:
        """Hash file contents. Returns None if file exceeds max_size."""
        ...

    def hash_bytes(self, data: bytes) -> str:
        """Hash bytes."""
        ...


@runtime_checkable
class TextExtractor(Protocol):
    """Protocol for text extraction from files."""

    def can_extract(self, path: Path) -> bool:
        """Check if text can be extracted from this file type."""
        ...

    def extract(self, path: Path, max_chars: int | None = None) -> str | None:
        """Extract text content. Returns None if extraction fails."""
        ...
