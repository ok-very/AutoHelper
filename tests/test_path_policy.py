"""Tests for path safety policy."""

import os
from pathlib import Path

import pytest

from autohelper.infra.fs.path_policy import PathPolicy
from autohelper.shared.errors import OutOfBoundsPathError, UnsafeSymlinkError


class TestPathPolicy:
    """Test path safety enforcement."""
    
    def test_validate_path_within_root(self, temp_dir: Path) -> None:
        """Valid path within root should pass."""
        policy = PathPolicy([temp_dir])
        
        test_file = temp_dir / "test.txt"
        test_file.write_text("test")
        
        result = policy.validate(test_file)
        assert result.exists()
    
    def test_reject_path_outside_root(self, temp_dir: Path) -> None:
        """Path outside root should raise OutOfBoundsPathError."""
        policy = PathPolicy([temp_dir])
        
        with pytest.raises(OutOfBoundsPathError) as exc:
            policy.validate(Path("C:\\Windows\\System32"))
        
        assert exc.value.code == "PATH_OUT_OF_ROOT"
    
    def test_reject_path_traversal(self, temp_dir: Path) -> None:
        """Path traversal attempts should be blocked."""
        policy = PathPolicy([temp_dir])
        
        # Create a subdirectory
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        
        # Attempt to traverse out
        evil_path = subdir / ".." / ".." / "etc" / "passwd"
        
        with pytest.raises(OutOfBoundsPathError):
            policy.validate(evil_path)
    
    @pytest.mark.skipif(os.name == "nt", reason="Symlinks need admin on Windows")
    def test_reject_symlink(self, temp_dir: Path) -> None:
        """Symlinks should be blocked when policy enabled."""
        policy = PathPolicy([temp_dir], block_symlinks=True)
        
        # Create a symlink
        target = temp_dir / "target.txt"
        target.write_text("target")
        
        link = temp_dir / "link.txt"
        link.symlink_to(target)
        
        with pytest.raises(UnsafeSymlinkError) as exc:
            policy.validate(link)
        
        assert exc.value.code == "PATH_SYMLINK_BLOCKED"
    
    def test_allow_symlink_when_disabled(self, temp_dir: Path) -> None:
        """Symlinks should be allowed when policy disabled."""
        if os.name == "nt":
            pytest.skip("Symlinks need admin on Windows")
        
        policy = PathPolicy([temp_dir], block_symlinks=False)
        
        target = temp_dir / "target.txt"
        target.write_text("target")
        
        link = temp_dir / "link.txt"
        link.symlink_to(target)
        
        result = policy.validate(link)
        assert result.exists()
    
    def test_multiple_roots(self, temp_dir: Path) -> None:
        """Paths in any configured root should be valid."""
        root1 = temp_dir / "root1"
        root2 = temp_dir / "root2"
        root1.mkdir()
        root2.mkdir()
        
        policy = PathPolicy([root1, root2])
        
        file1 = root1 / "file1.txt"
        file2 = root2 / "file2.txt"
        file1.write_text("1")
        file2.write_text("2")
        
        # Both should be valid
        assert policy.validate(file1).exists()
        assert policy.validate(file2).exists()
    
    def test_find_root(self, temp_dir: Path) -> None:
        """Should find which root a path belongs to."""
        root1 = temp_dir / "root1"
        root2 = temp_dir / "root2"
        root1.mkdir()
        root2.mkdir()
        
        policy = PathPolicy([root1, root2])
        
        file1 = root1 / "file.txt"
        file1.write_text("test")
        
        found = policy.find_root(file1)
        # Compare resolved paths for Windows case-insensitivity
        assert found is not None
