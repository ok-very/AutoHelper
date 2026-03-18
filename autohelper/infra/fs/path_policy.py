"""
Path safety policy - root allowlist, canonicalization, symlink blocking.
Critical security layer for all filesystem operations.
"""

import os
from pathlib import Path

from autohelper.shared.errors import OutOfBoundsPathError, UnsafeSymlinkError


class PathPolicy:
    """
    Enforces path safety rules:
    - Paths must be within configured root directories
    - Paths are canonicalized (no .., normalized separators)
    - Symlinks are blocked by default
    """

    def __init__(
        self,
        allowed_roots: list[Path],
        block_symlinks: bool = True,
    ) -> None:
        # Resolve and store canonical roots
        self._roots = [self._canonicalize(r) for r in allowed_roots]
        self._block_symlinks = block_symlinks

    @property
    def roots(self) -> list[Path]:
        """Get configured root directories."""
        return list(self._roots)

    def _canonicalize(self, path: Path) -> Path:
        """
        Canonicalize a path:
        - Resolve to absolute
        - Normalize separators
        - Resolve .. components
        - Case-normalize on Windows
        """
        resolved = path.resolve()
        # On Windows, normalize case for comparison
        if os.name == "nt":
            resolved = Path(str(resolved).lower())
        return resolved

    def validate(self, path: Path | str) -> Path:
        """
        Validate and canonicalize a path.

        Raises:
            OutOfBoundsPathError: If path is outside allowed roots
            UnsafeSymlinkError: If path is/contains a symlink and symlinks are blocked

        Returns:
            Canonicalized Path
        """
        path = Path(path) if isinstance(path, str) else path
        canonical = self._canonicalize(path)

        # Check symlink before root check (symlink could escape)
        if self._block_symlinks and self._is_or_contains_symlink(path):
            raise UnsafeSymlinkError(path=str(path))

        # Check if within any allowed root
        if not self._is_within_roots(canonical):
            raise OutOfBoundsPathError(path=str(path))

        return canonical

    def _is_within_roots(self, canonical: Path) -> bool:
        """Check if path is within any allowed root."""
        for root in self._roots:
            try:
                canonical.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    def _is_or_contains_symlink(self, path: Path) -> bool:
        """Check if path or any parent is a symlink."""
        # Check the path itself
        if path.is_symlink():
            return True

        # Check each component (except the root)
        parts = path.parts
        for i in range(1, len(parts)):
            partial = path.parents[i - 1]
            if partial.exists() and partial.is_symlink():
                return True

        return False

    def get_relative_path(self, path: Path | str, root: Path) -> str:
        """Get path relative to a specific root."""
        canonical = self.validate(path)
        return str(canonical.relative_to(self._canonicalize(root)))

    def find_root(self, path: Path | str) -> Path | None:
        """Find which root a path belongs to."""
        canonical = self.validate(path)
        for root in self._roots:
            try:
                canonical.relative_to(root)
                return root
            except ValueError:
                continue
        return None
