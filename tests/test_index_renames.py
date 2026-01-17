"""Tests for rename detection and file aliases."""

import time
import os
from pathlib import Path
import sqlite3

import pytest
from fastapi.testclient import TestClient

from autohelper.db import get_db
from autohelper.modules.index.service import IndexService
from autohelper.modules.search.service import SearchService

def get_file_id(db, path: str) -> str | None:
    """Helper to get file_id handling Windows casing."""
    row = db.execute("SELECT file_id FROM files WHERE canonical_path = ?", (path,)).fetchone()
    if not row:
         row = db.execute("SELECT file_id FROM files WHERE lower(canonical_path) = lower(?)", (path,)).fetchone()
    return row["file_id"] if row else None


class TestRenameDetection:
    """Test rename detection logic."""

    def test_rename_preserves_file_id_and_creates_alias(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """
        Verify that renaming a REFERENCED file preserves its ID and creates an alias.
        """
        # 1. Setup - Create file
        test_file = temp_dir / "test.txt"
        test_file.write_text("unique content for rename test")
        
        service = IndexService()
        service.rebuild_index(force_hash=True)
        
        db = get_db()
        canonical_original = str(test_file.resolve())
        
        # Get file_id
        file_id = get_file_id(db, canonical_original)
        assert file_id is not None
        
        # 2. Add Reference
        db.execute(
            "INSERT INTO refs (ref_id, file_id, canonical_path) VALUES (?, ?, ?)",
            ("ref1", file_id, canonical_original)
        )
        db.commit()
        
        # 3. Rename file
        new_file = temp_dir / "renamed.txt"
        test_file.rename(new_file)
        canonical_new = str(new_file.resolve())
        
        # 4. Rebuild Index
        service.rebuild_index(force_hash=True)
        
        # 5. Assertions
        
        # A. File ID preserved in 'files' table
        row_new = db.execute("SELECT file_id, canonical_path FROM files WHERE file_id = ?", (file_id,)).fetchone()
        assert row_new is not None
        assert row_new["canonical_path"].lower() == canonical_new.lower()
        
        # B. Alias created
        row_alias = db.execute(
            "SELECT * FROM file_aliases WHERE file_id = ? AND lower(old_canonical_path) = lower(?)", 
            (file_id, canonical_original)
        ).fetchone()
        assert row_alias is not None
        assert row_alias["new_canonical_path"].lower() == canonical_new.lower()
        
        # C. Ref updated
        row_ref = db.execute("SELECT canonical_path FROM refs WHERE ref_id = ?", ("ref1",)).fetchone()
        assert row_ref["canonical_path"].lower() == canonical_new.lower()

    def test_rename_chain_resolution(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """
        Verify A -> B -> C rename chain allows searching by A or B to find C.
        """
        # 1. Setup A
        file_a = temp_dir / "a.txt"
        file_a.write_text("chain content")
        
        service = IndexService()
        service.rebuild_index(force_hash=True)
        
        db = get_db()
        canonical_a = str(file_a.resolve())
        file_id = get_file_id(db, canonical_a)
        
        # Add Reference
        db.execute("INSERT INTO refs (ref_id, file_id, canonical_path) VALUES (?, ?, ?)", ("ref_chain", file_id, canonical_a))
        db.commit()
        
        # 2. Rename A -> B
        file_b = temp_dir / "b.txt"
        file_a.rename(file_b)
        service.rebuild_index(force_hash=True)
        canonical_b = str(file_b.resolve())
        
        # 3. Rename B -> C
        file_c = temp_dir / "c.txt"
        file_b.rename(file_c)
        service.rebuild_index(force_hash=True)
        canonical_c = str(file_c.resolve())
        
        # 4. Search Verification
        search_service = SearchService()
        
        # Search for A (Oldest name)
        res_a = search_service.search("a.txt")
        assert len(res_a.items) >= 1
        match_a = next((x for x in res_a.items if x.file_id == file_id), None)
        assert match_a is not None
        assert match_a.path.lower() == canonical_c.lower()
        assert match_a.matched_alias is True
        assert match_a.alias_of.lower() == canonical_a.lower()
        
        # Search for B (Intermediate name)
        res_b = search_service.search("b.txt")
        assert len(res_b.items) >= 1
        match_b = next((x for x in res_b.items if x.file_id == file_id), None)
        assert match_b is not None
        assert match_b.path.lower() == canonical_c.lower()
        assert match_b.matched_alias is True
        assert match_b.alias_of.lower() == canonical_b.lower()
        
        # Search for C (Current name)
        res_c = search_service.search("c.txt")
        assert len(res_c.items) >= 1
        match_c = next((x for x in res_c.items if x.file_id == file_id), None)
        assert match_c is not None
        assert match_c.path.lower() == canonical_c.lower()
        assert match_c.matched_alias is False # Direct match

    def test_unreferenced_file_is_treated_as_new(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """
        Verify that an unreferenced file is NOT tracked for renames (old deleted, new created).
        """
        # 1. Setup
        test_file = temp_dir / "untracked.txt"
        test_file.write_text("untracked content")
        
        service = IndexService()
        service.rebuild_index(force_hash=True)
        
        db = get_db()
        canonical_old = str(test_file.resolve())
        old_id = get_file_id(db, canonical_old)
        
        # NO Reference created
        
        # 2. Rename
        new_file = temp_dir / "untracked_new.txt"
        test_file.rename(new_file)
        
        # 3. Rebuild
        service.rebuild_index(force_hash=True)
        
        # 4. Assertions
        # Old ID should be gone
        row_old = db.execute("SELECT * FROM files WHERE file_id = ?", (old_id,)).fetchone()
        assert row_old is None
        
        # New file should have NEW ID
        canonical_new = str(new_file.resolve())
        row_new = db.execute("SELECT file_id FROM files WHERE canonical_path = ?", (canonical_new,)).fetchone()
        if not row_new:
             row_new = db.execute("SELECT file_id FROM files WHERE lower(canonical_path) = lower(?)", (canonical_new,)).fetchone()
        assert row_new is not None
        assert row_new["file_id"] != old_id
        
        # No alias created
        row_alias = db.execute("SELECT * FROM file_aliases WHERE old_canonical_path = ?", (canonical_old,)).fetchone()
        assert row_alias is None
