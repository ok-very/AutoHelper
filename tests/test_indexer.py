"""Tests for the indexer service."""

import json
import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from autohelper.db import get_db
from autohelper.modules.index.service import IndexService
from autohelper.shared.errors import ConflictError


class TestIndexService:
    """Test index service logic."""
    
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
        result = service.rebuild_index()
        
        assert result.status == "completed"
        # Check files indexed via DB
        db = get_db()
        files = db.execute("SELECT count(*) as c FROM files").fetchone()["c"]
        assert files >= 3

    def test_rebuild_with_specific_root_id(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """rebuild_index(specific_root_id=...) only indexes the requested root."""
        # Create two roots
        root1_path = temp_dir / "root1"
        root1_path.mkdir()
        (root1_path / "file1.txt").write_text("root1")
        
        root2_path = temp_dir / "root2"
        root2_path.mkdir()
        (root2_path / "file2.txt").write_text("root2")
        
        # Register both roots manually (since test_settings only has one allowed root usually)
        # But we need to add them to DB. 
        # Note: IndexService uses PathPolicy(settings.allowed_roots). 
        # If we want to scan multiple roots, they must be in allowed_roots or subdirs of it.
        # Temp dir IS the allowed root in tests. So root1 and root2 are subdirs.
        # But we want them to be registered as separate Roots in db.
        
        from autohelper.shared.ids import generate_root_id
        db = get_db()
        r1_id = generate_root_id()
        r2_id = generate_root_id()
        
        db.execute("INSERT INTO roots (root_id, path, enabled) VALUES (?, ?, 1)", (r1_id, str(root1_path)))
        db.execute("INSERT INTO roots (root_id, path, enabled) VALUES (?, ?, 1)", (r2_id, str(root2_path)))
        db.commit()
        
        service = IndexService()
        # Mock policy to allow these new roots if strictly validated?
        # The service uses: self.policy = PathPolicy(self.settings.get_allowed_roots())
        # In test_settings, allowed_roots=[temp_dir].
        # root1_path is relative to temp_dir, so it is allowed?
        # Actually PathPolicy roots are top level.
        # But let's see if we can just run it. The service checks `roots` table.
        # The service loops over `roots` table.
        
        # Act: rebuild index only for root1
        service.rebuild_index(specific_root_id=r1_id)
        
        # Assert
        files_r1 = db.execute("SELECT count(*) as c FROM files WHERE root_id = ?", (r1_id,)).fetchone()["c"]
        files_r2 = db.execute("SELECT count(*) as c FROM files WHERE root_id = ?", (r2_id,)).fetchone()["c"]
        
        assert files_r1 >= 1
        assert files_r2 == 0, "Root 2 should NOT be scanned"

    def test_rebuild_with_specific_root_id_not_found(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """rebuild_index with invalid root_id raises NotFound (404 via API)."""
        service = IndexService()
        from autohelper.shared.errors import NotFoundError
        
        with pytest.raises(NotFoundError):
            service.rebuild_index(specific_root_id="bad_id")
    
    def test_rebuild_indexes_files(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """Rebuild should create file entries in database."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")
        
        service = IndexService()
        service.rebuild_index()
        
        # Check file was indexed
        db = get_db()
        canonical = str(test_file.resolve())
        # Try exact match first
        file_entry = db.execute("SELECT * FROM files WHERE canonical_path = ?", (canonical,)).fetchone()
        
        # Fallback for Windows casing
        if not file_entry:
            file_entry = db.execute("SELECT * FROM files WHERE lower(canonical_path) = lower(?)", (canonical,)).fetchone()
        
        assert file_entry is not None
        assert file_entry["ext"] == ".txt"
        assert file_entry["size"] == len("test content")

    def test_rebuild_includes_content_hash_for_small_files(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """rebuild(force_hash=True) should set content_hash for small files."""
        test_file = temp_dir / "hash_me.txt"
        content = "small file content"
        test_file.write_text(content)

        service = IndexService()
        service.rebuild_index(force_hash=True)

        db = get_db()
        canonical = str(test_file.resolve())
        file_entry = db.execute("SELECT * FROM files WHERE canonical_path = ?", (canonical,)).fetchone()
        if not file_entry:
             file_entry = db.execute("SELECT * FROM files WHERE lower(canonical_path) = lower(?)", (canonical,)).fetchone()

        assert file_entry is not None
        assert file_entry["content_hash"] is not None

    def test_rebuild_skips_content_hash_for_large_files_if_not_forced(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """Standard rebuild should NOT hash large files unless forced."""
        test_file = temp_dir / "large_file.txt"
        # 1MB + 1 byte
        content = "x" * (1_000_000 + 1)
        test_file.write_text(content)

        service = IndexService()
        service.rebuild_index()

        db = get_db()
        canonical = str(test_file.resolve())
        row = db.execute("SELECT content_hash FROM files WHERE canonical_path = ?", (canonical,)).fetchone()
        if not row:
             row = db.execute("SELECT content_hash FROM files WHERE lower(canonical_path) = lower(?)", (canonical,)).fetchone()
        
        assert row is not None
        assert row["content_hash"] is None, "Large file should not be hashed by default"

        # Force hash
        service.rebuild_index(force_hash=True)
        row = db.execute("SELECT content_hash FROM files WHERE canonical_path = ? OR lower(canonical_path) = lower(?)", (canonical, canonical)).fetchone()
        assert row["content_hash"] is not None, "Large file SHOULD be hashed when forced"
    
    def test_rebuild_handles_nested_dirs(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """Rebuild should handle deeply nested directories."""
        # Create nested structure
        deep = temp_dir / "a" / "b" / "c" / "d"
        deep.mkdir(parents=True)
        (deep / "deep.txt").write_text("deep file")
        
        service = IndexService()
        result = service.rebuild_index()
        
        db = get_db()
        # Check deep file
        file_entry = db.execute("SELECT * FROM files WHERE rel_path = ?", ("a\\b\\c\\d\\deep.txt",)).fetchone()
        # If linux use forward slash, but test runs on Windows (user OS)
        if not file_entry:
             file_entry = db.execute("SELECT * FROM files WHERE rel_path = ?", ("a/b/c/d/deep.txt",)).fetchone()
             
        assert file_entry is not None
    
    def test_rescan_removes_deleted_files(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """Rescan should remove files that no longer exist."""
        test_file = temp_dir / "temporary.txt"
        test_file.write_text("temp")
        
        service = IndexService()
        service.rebuild_index()
        
        db = get_db()
        canonical = str(test_file.resolve())
        # Verify file is indexed
        row = db.execute("SELECT file_id FROM files WHERE canonical_path = ?", (canonical,)).fetchone()
        if not row:
            row = db.execute("SELECT file_id FROM files WHERE lower(canonical_path) = lower(?)", (canonical,)).fetchone()
        assert row is not None
        
        # Delete file and rescan
        test_file.unlink()
        service.rescan()
        
        # File should be removed from index
        row = db.execute("SELECT file_id FROM files WHERE canonical_path = ?", (canonical,)).fetchone()
        if not row:
             row = db.execute("SELECT file_id FROM files WHERE lower(canonical_path) = lower(?)", (canonical,)).fetchone()
        assert row is None

    def test_rescan_removes_deleted_directories(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """Rescan should remove files in deleted directories."""
        nested_dir = temp_dir / "nested" / "subdir"
        nested_dir.mkdir(parents=True)
        nested_file = nested_dir / "nested_file.txt"
        nested_file.write_text("nested content")

        service = IndexService()
        service.rebuild_index()

        db = get_db()
        canonical = str(nested_file.resolve())
        row = db.execute("SELECT file_id FROM files WHERE canonical_path = ?", (canonical,)).fetchone()
        if not row:
            row = db.execute("SELECT file_id FROM files WHERE lower(canonical_path) = lower(?)", (canonical,)).fetchone()
        assert row is not None

        # Delete entire directory tree and rescan
        shutil.rmtree(temp_dir / "nested")
        service.rescan()

        # File should be removed from index
        row = db.execute("SELECT file_id FROM files WHERE canonical_path = ?", (canonical,)).fetchone()
        if not row:
             row = db.execute("SELECT file_id FROM files WHERE lower(canonical_path) = lower(?)", (canonical,)).fetchone()
        assert row is None
    
    def test_get_status(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """Get status should return index information."""
        service = IndexService()
        
        # Before indexing
        status = service.get_status()
        assert status["is_running"] is False
        assert status["last_completed"] is None
        
        # After indexing
        service.rebuild_index()
        status = service.get_status()
        assert status["is_running"] is False
        assert status["last_completed"] is not None
        assert status["last_completed"]["status"] == "completed"

    def test_get_status_when_running(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """Get status should show running state."""
        from autohelper.shared.ids import generate_index_run_id
        
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
        
        # Verify side effect
        db = get_db()
        c = db.execute("SELECT count(*) as c FROM files").fetchone()["c"]
        assert c >= 1

    def test_rebuild_endpoint_propagates_hash_params(
        self, client: TestClient, temp_dir: Path
    ) -> None:
        """Endpoint /index/rebuild should honor force_hash."""
        test_file = temp_dir / "endpoint_hash.txt"
        content = "endpoint hash content"
        test_file.write_text(content)

        response = client.post(
            "/index/rebuild",
            json={"force_hash": True},
        )
        assert response.status_code == 200

        db = get_db()
        canonical = str(test_file.resolve())
        file_entry = db.execute("SELECT * FROM files WHERE canonical_path = ?", (canonical,)).fetchone()
        if not file_entry:
            file_entry = db.execute("SELECT * FROM files WHERE lower(canonical_path) = lower(?)", (canonical,)).fetchone()

        assert file_entry is not None
        assert file_entry["content_hash"] is not None

    def test_rebuild_endpoint_conflict_returns_409(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """POST /index/rebuild should return 409 when running."""
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

    def test_rescan_endpoint_conflict_returns_409(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """POST /index/rescan should return 409 when running."""
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
    
    def test_status_endpoint(self, client: TestClient, temp_dir: Path) -> None:
        """GET /index/status should return status."""
        (temp_dir / "status_test.txt").write_text("status test")
        
        client.post("/index/rebuild", json={})
        
        response = client.get("/index/status")
        
        assert response.status_code == 200
        data = response.json()
        assert "is_running" in data
        assert "total_roots" in data
        assert "total_files" in data
        assert data["last_completed"]["status"] == "completed"
    
    def test_roots_endpoint(
        self, client: TestClient, temp_dir: Path
    ) -> None:
        """GET /index/roots should return root stats."""
        (temp_dir / "roots_test.txt").write_text("roots test content")
        
        client.post("/index/rebuild", json={})
        
        response = client.get("/index/roots")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        
        root_item = data[0]
        assert "root_id" in root_item
        assert "path" in root_item
        assert "file_count" in root_item
