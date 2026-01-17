"""Tests for the reference service."""

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from autohelper.db import get_db
from autohelper.modules.index.service import IndexService
from autohelper.modules.reference.service import ReferenceService


class TestReferenceService:
    """Test reference logic."""
    
    def test_register_creates_ref(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """Registering a new path should create a reference."""
        # Setup file
        path = temp_dir / "ref_test.txt"
        path.write_text("content")
        IndexService().rebuild_index()
        
        service = ReferenceService()
        req = type("Req", (), {"path": str(path.resolve()), "work_item_id": "w1", "context_id": "c1", "note": "test"})()
        
        ref = service.register(req)
        
        assert ref.ref_id is not None
        assert ref.path == str(path.resolve())
        
        # Verify DB
        db = get_db()
        row = db.execute("SELECT * FROM refs WHERE ref_id = ?", (ref.ref_id,)).fetchone()
        assert row is not None
        assert row["file_id"] is not None # Linked to indexed file
        
    def test_resolve_exact_match(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """Resolve should return path if it exists exact match."""
        path = temp_dir / "exact.txt"
        path.write_text("content")
        
        # Register
        IndexService().rebuild_index()
        service = ReferenceService()
        req = type("Req", (), {"path": str(path.resolve()), "work_item_id": None, "context_id": None, "note": None})()
        ref = service.register(req)
        
        # Resolve
        res = service.resolve(ref.ref_id)
        
        assert res.found is True
        assert res.strategy == "exact"
        assert res.path == str(path.resolve())

    def test_resolve_hash_recovery(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """Resolve should find file by hash if moved."""
        # 1. Create original file with unique content
        original_name = "original.txt"
        unique_content = "unique content for hash match 12345"
        p1 = temp_dir / original_name
        p1.write_text(unique_content)
        
        # 2. Index & Register (force hash)
        idx = IndexService()
        idx.rebuild_index(force_hash=True)
        
        srv = ReferenceService()
        canonical = str(p1.resolve())
        req = type("Req", (), {"path": canonical, "work_item_id": None, "context_id": None, "note": None})()
        ref = srv.register(req)
        
        # Verify we captured hash
        db = get_db()
        row = db.execute("SELECT content_hash FROM refs WHERE ref_id = ?", (ref.ref_id,)).fetchone()
        assert row["content_hash"] is not None
        
        # 3. Move file (Delete old, create new with same content)
        p1.unlink()
        p2 = temp_dir / "moved.txt"
        p2.write_text(unique_content)
        
        # 4. Re-index to capture new location
        idx.rebuild_index(force_hash=True)
        
        # 5. Resolve old ref
        res = srv.resolve(ref.ref_id)
        
        # 6. Should find new path via hash
        assert res.found is True
        assert res.strategy == "hash"
        # Case insensitive check for Windows robustness
        assert str(p2.resolve()).lower() in (res.path or "").lower()

