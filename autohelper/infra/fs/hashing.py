"""
Content hashing implementation.
"""

import hashlib
from pathlib import Path


class SHA256Hasher:
    """SHA-256 content hasher."""
    
    def __init__(self, chunk_size: int = 65536) -> None:
        self._chunk_size = chunk_size
    
    def hash_file(self, path: Path, max_size: int | None = None) -> str | None:
        """
        Hash file contents using SHA-256.
        
        Args:
            path: File to hash
            max_size: Skip files larger than this (bytes)
        
        Returns:
            Hex digest or None if file exceeds max_size
        """
        if max_size is not None:
            size = path.stat().st_size
            if size > max_size:
                return None
        
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(self._chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def hash_bytes(self, data: bytes) -> str:
        """Hash bytes using SHA-256."""
        return hashlib.sha256(data).hexdigest()


# Default hasher instance
hasher = SHA256Hasher()
