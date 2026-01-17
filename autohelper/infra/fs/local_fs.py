"""
Local filesystem implementation of FileSystem protocol.
"""

import os
from pathlib import Path

from .protocols import FileStat


class LocalFileSystem:
    """Real filesystem implementation."""
    
    def stat(self, path: Path) -> FileStat:
        """Get file stat info."""
        st = path.stat()
        
        # OneDrive Files On-Demand: detect offline (cloud-only) files on Windows
        # FILE_ATTRIBUTE_OFFLINE (0x1000) indicates file content is not locally available
        is_offline = False
        if hasattr(st, 'st_file_attributes'):  # Windows only
            FILE_ATTRIBUTE_OFFLINE = 0x1000
            is_offline = bool(st.st_file_attributes & FILE_ATTRIBUTE_OFFLINE)
        
        return FileStat(
            path=path,
            size=st.st_size,
            mtime_ns=st.st_mtime_ns,
            is_dir=path.is_dir(),
            is_symlink=path.is_symlink(),
            is_offline=is_offline,
        )
    
    def exists(self, path: Path) -> bool:
        """Check if path exists."""
        return path.exists()
    
    def is_dir(self, path: Path) -> bool:
        """Check if path is a directory."""
        return path.is_dir()
    
    def is_file(self, path: Path) -> bool:
        """Check if path is a file."""
        return path.is_file()
    
    def is_symlink(self, path: Path) -> bool:
        """Check if path is a symlink."""
        return path.is_symlink()
    
    def read_bytes(self, path: Path) -> bytes:
        """Read file contents as bytes."""
        return path.read_bytes()
    
    def read_text(self, path: Path, encoding: str = "utf-8") -> str:
        """Read file contents as text."""
        return path.read_text(encoding=encoding)
    
    def iterdir(self, path: Path) -> list[Path]:
        """List directory contents."""
        return list(path.iterdir())
    
    def walk(self, path: Path) -> list[tuple[Path, list[str], list[str]]]:
        """Walk directory tree."""
        results: list[tuple[Path, list[str], list[str]]] = []
        for root, dirs, files in os.walk(path):
            results.append((Path(root), dirs, files))
        return results


# Singleton instance
local_fs = LocalFileSystem()
