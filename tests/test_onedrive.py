"""
Tests for OneDrive Files On-Demand support.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from autohelper.infra.fs.protocols import FileStat


class MockStat:
    """Mock stat_result with Windows file attributes."""
    
    def __init__(
        self,
        st_size: int = 1024,
        st_mtime_ns: int = 1000000000,
        st_file_attributes: int | None = None,
    ):
        self.st_size = st_size
        self.st_mtime_ns = st_mtime_ns
        if st_file_attributes is not None:
            self.st_file_attributes = st_file_attributes


class TestFileStat:
    """Tests for FileStat with is_offline field."""
    
    def test_default_is_not_offline(self) -> None:
        """is_offline should default to False."""
        stat = FileStat(
            path=Path("test.txt"),
            size=100,
            mtime_ns=1000000000,
            is_dir=False,
            is_symlink=False,
        )
        assert stat.is_offline is False
    
    def test_explicit_offline_true(self) -> None:
        """is_offline can be set to True."""
        stat = FileStat(
            path=Path("test.txt"),
            size=100,
            mtime_ns=1000000000,
            is_dir=False,
            is_symlink=False,
            is_offline=True,
        )
        assert stat.is_offline is True


class TestLocalFileSystemOfflineDetection:
    """Tests for LocalFileSystem offline file detection."""
    
    def test_detects_offline_on_windows(self) -> None:
        """Should detect FILE_ATTRIBUTE_OFFLINE on Windows."""
        from autohelper.infra.fs.local_fs import LocalFileSystem
        
        fs = LocalFileSystem()
        FILE_ATTRIBUTE_OFFLINE = 0x1000
        
        mock_stat = MockStat(st_file_attributes=FILE_ATTRIBUTE_OFFLINE)
        
        with patch.object(Path, 'stat', return_value=mock_stat):
            with patch.object(Path, 'is_dir', return_value=False):
                with patch.object(Path, 'is_symlink', return_value=False):
                    result = fs.stat(Path("cloud_file.txt"))
                    assert result.is_offline is True
    
    def test_not_offline_without_attribute(self) -> None:
        """Should not be offline if FILE_ATTRIBUTE_OFFLINE not set."""
        from autohelper.infra.fs.local_fs import LocalFileSystem
        
        fs = LocalFileSystem()
        
        mock_stat = MockStat(st_file_attributes=0)  # No offline flag
        
        with patch.object(Path, 'stat', return_value=mock_stat):
            with patch.object(Path, 'is_dir', return_value=False):
                with patch.object(Path, 'is_symlink', return_value=False):
                    result = fs.stat(Path("local_file.txt"))
                    assert result.is_offline is False
    
    def test_non_windows_always_not_offline(self) -> None:
        """On non-Windows systems, is_offline should always be False."""
        from autohelper.infra.fs.local_fs import LocalFileSystem
        
        fs = LocalFileSystem()
        
        # Mock stat result without st_file_attributes (non-Windows)
        # Create a simple mock without the attribute at all
        class MockStatNoAttributes:
            st_size = 1024
            st_mtime_ns = 1000000000
        
        mock_stat = MockStatNoAttributes()
        
        with patch.object(Path, 'stat', return_value=mock_stat):
            with patch.object(Path, 'is_dir', return_value=False):
                with patch.object(Path, 'is_symlink', return_value=False):
                    result = fs.stat(Path("any_file.txt"))
                    assert result.is_offline is False


class TestOneDriveManager:
    """Tests for OneDriveManager utilities."""
    
    def test_is_available_on_windows(self) -> None:
        """OneDriveManager should be available on Windows."""
        from autohelper.infra.fs.onedrive import OneDriveManager

        manager = OneDriveManager()

        # Force Windows mode for testing
        manager._is_windows = True

        # Mock the kernel32 attribute check to simulate Windows availability
        manager._kernel32 = MagicMock()

        # Now is_available should return True
        assert manager.is_available is True
    
    def test_is_offline_file_false_when_not_available(self) -> None:
        """is_offline_file should return False when not on Windows."""
        from autohelper.infra.fs.onedrive import OneDriveManager
        
        manager = OneDriveManager()
        manager._is_windows = False
        
        result = manager.is_offline_file(Path("test.txt"))
        assert result is False
    
    def test_free_up_space_returns_false_when_not_available(self) -> None:
        """free_up_space should return False when not on Windows."""
        from autohelper.infra.fs.onedrive import OneDriveManager
        
        manager = OneDriveManager()
        manager._is_windows = False
        
        result = manager.free_up_space(Path("test.txt"))
        assert result is False


class TestIndexServiceOfflineHandling:
    """Tests for IndexService handling of offline files."""

    def test_upsert_skips_hash_for_offline(self, tmp_path) -> None:
        """_upsert_file should skip hashing for offline files."""
        from unittest.mock import MagicMock, patch

        # Create mocks for dependencies
        mock_db = MagicMock()
        mock_settings = MagicMock()
        mock_settings.get_allowed_roots.return_value = [tmp_path]
        mock_settings.block_symlinks = False

        with patch('autohelper.modules.index.service.get_settings', return_value=mock_settings):
            with patch('autohelper.modules.index.service.get_db', return_value=mock_db):
                with patch('autohelper.modules.index.service.hasher') as mock_hasher:
                    from autohelper.modules.index.service import IndexService

                    service = IndexService()

                    # Create an offline file stat
                    mock_stat = MagicMock()
                    mock_stat.is_offline = True
                    mock_stat.size = 1024
                    mock_stat.mtime_ns = 1000000000

                    # Call _upsert_file with offline stat
                    service._upsert_file(
                        root_id="test_root",
                        root_path=tmp_path,
                        rel_path="test.txt",
                        stat=mock_stat,
                        existing_id=None,
                        force_hash=False
                    )

                    # Assert hasher was never called for offline file
                    mock_hasher.hash_file.assert_not_called()

    def test_upsert_hashes_online_file(self, tmp_path) -> None:
        """_upsert_file should hash online files (when small enough)."""
        from unittest.mock import MagicMock, patch

        mock_db = MagicMock()
        mock_settings = MagicMock()
        mock_settings.get_allowed_roots.return_value = [tmp_path]
        mock_settings.block_symlinks = False

        with patch('autohelper.modules.index.service.get_settings', return_value=mock_settings):
            with patch('autohelper.modules.index.service.get_db', return_value=mock_db):
                with patch('autohelper.modules.index.service.hasher') as mock_hasher:
                    mock_hasher.hash_file.return_value = "abc123"
                    from autohelper.modules.index.service import IndexService

                    service = IndexService()

                    # Create an online (not offline) file stat under size limit
                    mock_stat = MagicMock()
                    mock_stat.is_offline = False
                    mock_stat.size = 1024  # Under 1MB threshold
                    mock_stat.mtime_ns = 1000000000

                    service._upsert_file(
                        root_id="test_root",
                        root_path=tmp_path,
                        rel_path="test.txt",
                        stat=mock_stat,
                        existing_id=None,
                        force_hash=False
                    )

                    # Assert hasher was called for online file
                    mock_hasher.hash_file.assert_called_once()
