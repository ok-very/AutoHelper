"""Tests for the indexer service."""

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from autohelper.db.repos import FileRepository
from autohelper.modules.index.service import IndexService
from autohelper.shared.errors import ConflictError


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

    def test_rebuild_includes_content_hash_for_small_files(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """rebuild(include_hash=True) should set content_hash for small files."""
        test_file = temp_dir / "hash_me.txt"
        content = "small file content"
        test_file.write_text(content)

        service = IndexService()
        service.rebuild(include_hash=True, max_hash_size=len(content.encode()) + 100)

        repo = FileRepository()
        file_entry = repo.get_by_path(str(test_file))

        assert file_entry is not None
        assert file_entry["content_hash"] is not None

    def test_rebuild_skips_content_hash_for_large_files(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """rebuild(include_hash=True) should not hash files larger than limit."""
        test_file = temp_dir / "too_big_to_hash.txt"
        max_hash_size = 100
        content = "x" * (max_hash_size + 50)
        test_file.write_text(content)

        service = IndexService()
        service.rebuild(include_hash=True, max_hash_size=max_hash_size)

        repo = FileRepository()
        file_entry = repo.get_by_path(str(test_file))

        assert file_entry is not None
        assert file_entry["content_hash"] is None
    
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

    def test_rescan_removes_deleted_directories(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """Rescan should remove directories and their contents that no longer exist."""
        nested_dir = temp_dir / "nested" / "subdir"
        nested_dir.mkdir(parents=True)
        nested_file = nested_dir / "nested_file.txt"
        nested_file.write_text("nested content")

        service = IndexService()
        service.rebuild()

        repo = FileRepository()
        # Verify directory and file are indexed
        assert repo.get_by_path(str(nested_dir)) is not None
        assert repo.get_by_path(str(nested_file)) is not None

        # Delete entire directory tree and rescan
        shutil.rmtree(temp_dir / "nested")
        service.rescan()

        # Directory and its nested file should be removed from index
        assert repo.get_by_path(str(nested_dir)) is None
        assert repo.get_by_path(str(nested_file)) is None
    
    def test_get_status(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """Get status should return index information for idle, running, and completed."""
        service = IndexService()
        
        # Before any indexing, service should be idle
        status = service.get_status()
        assert status["is_running"] is False
        assert status["current_run"] is None
        assert status["last_completed"] is None
        
        # After indexing
        service.rebuild()
        status = service.get_status()
        assert status["is_running"] is False
        assert status["last_completed"] is not None
        assert status["last_completed"]["status"] == "completed"

    def test_get_status_when_running(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """Get status should show running state when index is in progress."""
        from autohelper.db import get_db
        from autohelper.shared.ids import generate_index_run_id
        
        # Insert a running index run
        db = get_db()
        run_id = generate_index_run_id()
        db.execute(
            "INSERT INTO index_runs (index_run_id, kind, status) VALUES (?, ?, ?)",
            (run_id, "full", "running"),
        )
        db.commit()
        
        service = IndexService()
        status = service.get_status()
        
        assert status["is_running"] is True
        assert status["current_run"] is not None
        assert status["current_run"]["status"] == "running"

    def test_rebuild_conflict_raises_conflict_error(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """Rebuild should raise ConflictError when an index run is already running."""
        from autohelper.db import get_db
        from autohelper.shared.ids import generate_index_run_id
        
        # Insert a running index run
        db = get_db()
        run_id = generate_index_run_id()
        db.execute(
            "INSERT INTO index_runs (index_run_id, kind, status) VALUES (?, ?, ?)",
            (run_id, "full", "running"),
        )
        db.commit()

        service = IndexService()

        with pytest.raises(ConflictError):
            service.rebuild()


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

    def test_rebuild_endpoint_propagates_hash_params(
        self, client: TestClient, temp_dir: Path
    ) -> None:
        """Endpoint /index/rebuild should honor include_content_hash and max_file_size_mb."""
        test_file = temp_dir / "endpoint_hash.txt"
        content = "endpoint hash content"
        test_file.write_text(content)

        response = client.post(
            "/index/rebuild",
            json={"include_content_hash": True, "max_file_size_mb": 1},
        )
        assert response.status_code == 200

        repo = FileRepository()
        file_entry = repo.get_by_path(str(test_file))

        assert file_entry is not None
        assert file_entry["content_hash"] is not None

    def test_rebuild_endpoint_conflict_returns_409(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """POST /index/rebuild should return 409 when an index run is already running."""
        from autohelper.db import get_db
        from autohelper.shared.ids import generate_index_run_id
        
        db = get_db()
        run_id = generate_index_run_id()
        db.execute(
            "INSERT INTO index_runs (index_run_id, kind, status) VALUES (?, ?, ?)",
            (run_id, "full", "running"),
        )
        db.commit()

        response = client.post("/index/rebuild", json={})
        assert response.status_code == 409

        payload = response.json()
        assert "detail" in payload

    def test_rescan_endpoint_conflict_returns_409(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """POST /index/rescan should return 409 when an index run is already running."""
        from autohelper.db import get_db
        from autohelper.shared.ids import generate_index_run_id
        
        db = get_db()
        run_id = generate_index_run_id()
        db.execute(
            "INSERT INTO index_runs (index_run_id, kind, status) VALUES (?, ?, ?)",
            (run_id, "full", "running"),
        )
        db.commit()

        response = client.post("/index/rescan", json={})
        assert response.status_code == 409

        payload = response.json()
        assert "detail" in payload
    
    def test_status_endpoint(self, client: TestClient, temp_dir: Path) -> None:
        """GET /index/status should return status after a rebuild."""
        (temp_dir / "status_test.txt").write_text("status test")
        
        # Trigger a rebuild to populate index status
        rebuild_response = client.post("/index/rebuild", json={})
        assert rebuild_response.status_code == 200
        
        response = client.get("/index/status")
        
        assert response.status_code == 200
        data = response.json()
        assert "is_running" in data
        assert "total_roots" in data
        assert "total_files" in data
        assert data["last_completed"] is not None
        assert data["last_completed"]["status"] == "completed"
        assert data["total_files"] >= 1
    
    def test_roots_endpoint(
        self, client: TestClient, temp_dir: Path
    ) -> None:
        """GET /index/roots should return root stats with expected structure."""
        # Create a file to ensure we have content
        (temp_dir / "roots_test.txt").write_text("roots test content")
        
        # First rebuild to populate
        client.post("/index/rebuild", json={})
        
        response = client.get("/index/roots")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        
        # Check structure of first item
        root_item = data[0]
        assert "root_id" in root_item
        assert "path" in root_item
        assert "file_count" in root_item
        assert "dir_count" in root_item
        assert "total_size" in root_item
        
        # At least one root should have files
        total_files = sum(r["file_count"] for r in data)
        assert total_files >= 1
