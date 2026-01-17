"""Tests for the indexer service."""

from pathlib import Path

from fastapi.testclient import TestClient

from autohelper.db.repos import FileRepository
from autohelper.modules.index.service import IndexService


class TestIndexService:
    """Test index service directly."""
    
    def test_rebuild_creates_index_run(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """Rebuild should create an index run record."""
        # Create some test files
        (temp_dir / "file1.txt").write_text("hello")
        (temp_dir / "file2.txt").write_text("world")
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        (subdir / "file3.txt").write_text("nested")
        
        service = IndexService()
        result = service.rebuild()
        
        assert result["status"] == "completed"
        assert result["files_indexed"] >= 3  # At least our 3 test files
        assert result["dirs_indexed"] >= 1  # At least subdir
        assert "index_run_id" in result
    
    def test_rebuild_indexes_files(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """Rebuild should create file entries in database."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")
        
        service = IndexService()
        service.rebuild()
        
        # Check file was indexed
        repo = FileRepository()
        file_entry = repo.get_by_path(str(test_file))
        
        assert file_entry is not None
        assert file_entry["ext"] == "txt"
        assert file_entry["size"] == len("test content")
    
    def test_rebuild_handles_nested_dirs(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """Rebuild should handle deeply nested directories."""
        # Create nested structure
        deep = temp_dir / "a" / "b" / "c" / "d"
        deep.mkdir(parents=True)
        (deep / "deep.txt").write_text("deep file")
        
        service = IndexService()
        result = service.rebuild()
        
        assert result["files_indexed"] >= 1  # At least our test file
        assert result["dirs_indexed"] >= 4  # At least a/b/c/d
        
        repo = FileRepository()
        file_entry = repo.get_by_path(str(deep / "deep.txt"))
        assert file_entry is not None
    
    def test_rescan_removes_deleted_files(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """Rescan should remove files that no longer exist."""
        test_file = temp_dir / "temporary.txt"
        test_file.write_text("temp")
        
        service = IndexService()
        service.rebuild()
        
        # Verify file is indexed
        repo = FileRepository()
        assert repo.get_by_path(str(test_file)) is not None
        
        # Delete file and rescan
        test_file.unlink()
        service.rescan()
        
        # File should be removed from index
        assert repo.get_by_path(str(test_file)) is None
    
    def test_get_status(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """Get status should return index information."""
        service = IndexService()
        
        # Before any indexing
        status = service.get_status()
        assert status["is_running"] is False
        
        # After indexing
        service.rebuild()
        status = service.get_status()
        assert status["last_completed"] is not None
        assert status["last_completed"]["status"] == "completed"


class TestIndexEndpoints:
    """Test index API endpoints."""
    
    def test_rebuild_endpoint(
        self, client: TestClient, temp_dir: Path
    ) -> None:
        """POST /index/rebuild should trigger rebuild."""
        (temp_dir / "api_test.txt").write_text("api test")
        
        response = client.post("/index/rebuild", json={})
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["files_indexed"] >= 1
    
    def test_status_endpoint(self, client: TestClient) -> None:
        """GET /index/status should return status."""
        response = client.get("/index/status")
        
        assert response.status_code == 200
        data = response.json()
        assert "is_running" in data
        assert "total_roots" in data
        assert "total_files" in data
    
    def test_roots_endpoint(
        self, client: TestClient, temp_dir: Path
    ) -> None:
        """GET /index/roots should return root stats."""
        # First rebuild to populate
        client.post("/index/rebuild", json={})
        
        response = client.get("/index/roots")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
