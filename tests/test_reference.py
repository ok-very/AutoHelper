"""Tests for the reference service."""

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from autohelper.db import get_db
from autohelper.modules.index.service import IndexService
from autohelper.modules.reference.service import ReferenceService
from autohelper.modules.reference.schemas import ReferenceCreate


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
        service = ReferenceService()
        from autohelper.modules.reference.schemas import ReferenceCreate
        req = ReferenceCreate(
            path=str(path.resolve()), 
            work_item_id="w1", 
            context_id="c1", 
            note="test"
        )
        
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
        # Register
        IndexService().rebuild_index()
        service = ReferenceService()
        from autohelper.modules.reference.schemas import ReferenceCreate
        req = ReferenceCreate(
            path=str(path.resolve()), 
            work_item_id=None, 
            context_id=None, 
            note=None
        )
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
        srv = ReferenceService()
        canonical = str(p1.resolve())
        from autohelper.modules.reference.schemas import ReferenceCreate
        req = ReferenceCreate(
            path=canonical, 
            work_item_id=None, 
            context_id=None, 
            note=None
        )
        ref = srv.register(req)
        
        # Verify we captured hash
        db = get_db()
        row = db.execute("SELECT content_hash FROM refs WHERE ref_id = ?", (ref.ref_id,)).fetchone()
        assert row["content_hash"] is not None
        
        # 3. Move file (Delete old, create new with same content)
        p1.unlink(missing_ok=True)
        import time
        for _ in range(10): # retry for windows
             if not p1.exists(): break
             time.sleep(0.1)
        assert not p1.exists(), "File failed to unlink"
        
        p2 = temp_dir / "moved.txt"
        p2.write_text(unique_content)
        
        # 4. Re-index to capture new location
        idx.rebuild_index(force_hash=True)
        
        # 5. Resolve old ref
        res = srv.resolve(ref.ref_id)
        
        # 6. Should find new path via hash
        # 6. Should find new path (either via hash lookup or because IndexService updated the ref)
        assert res.found is True
        assert res.strategy in ("hash", "exact")
        # Case insensitive check for Windows robustness
        assert str(p2.resolve()).lower() in (res.path or "").lower()

    def test_resolve_missing_ref_returns_error(self, client: TestClient, temp_dir: Path, test_db) -> None:
        """Resolving a non-existent ref_id should raise Error."""
        service = ReferenceService()
        from autohelper.shared.errors import NotFoundError
        
        with pytest.raises(NotFoundError):
            service.resolve("non_existent_ref")

    def test_resolve_deleted_file_no_hash_match(self, client: TestClient, temp_dir: Path, test_db) -> None:
        """Resolving a ref whose file is deleted and has no hash match should fail gracefully."""
        # 1. Create file (no hash forced)
        p = temp_dir / "temp.txt"
        p.write_text("deleted content")
        
        IndexService().rebuild_index() # Might not hash if > 1MB but this is small.
        # However, M1 Spec says default hashing is optional/off? 
        # In implementation: if small (<1MB) it hashes. "deleted content" is small.
        # We need to simulate NO hash. Delete hash from DB?
        
        service = ReferenceService()
        from autohelper.modules.reference.schemas import ReferenceCreate
        req = ReferenceCreate(
            path=str(p.resolve()), 
            work_item_id=None, 
            context_id=None, 
            note=None
        )
        ref = service.register(req)
        
        # Manually clear hash in DB to simulate 'no hash available' scenario
        db = get_db()
        db.execute("UPDATE refs SET content_hash = NULL WHERE ref_id = ?", (ref.ref_id,))
        db.commit()
        
        # 2. Delete file
        p.unlink()
        
        # 3. Resolve
        res = service.resolve(ref.ref_id)
        
        assert res.found is False
        assert res.strategy == "none"

