"""Repository for root directory operations."""

from pathlib import Path

from autohelper.db import get_db
from autohelper.shared.ids import generate_root_id


class RootRepository:
    """CRUD operations for roots table."""
    
    def create(self, path: Path, enabled: bool = True) -> str:
        """Create a new root entry. Returns root_id."""
        db = get_db()
        root_id = generate_root_id()
        
        db.execute(
            "INSERT INTO roots (root_id, path, enabled) VALUES (?, ?, ?)",
            (root_id, str(path.resolve()), int(enabled)),
        )
        db.commit()
        return root_id
    
    def get_by_id(self, root_id: str) -> dict | None:
        """Get root by ID."""
        db = get_db()
        cursor = db.execute(
            "SELECT root_id, path, enabled, created_at FROM roots WHERE root_id = ?",
            (root_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_by_path(self, path: Path) -> dict | None:
        """Get root by path."""
        db = get_db()
        cursor = db.execute(
            "SELECT root_id, path, enabled, created_at FROM roots WHERE path = ?",
            (str(path.resolve()),),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_or_create(self, path: Path) -> tuple[str, bool]:
        """Get existing root or create new. Returns (root_id, created)."""
        existing = self.get_by_path(path)
        if existing:
            return existing["root_id"], False
        return self.create(path), True
    
    def list_enabled(self) -> list[dict]:
        """List all enabled roots."""
        db = get_db()
        cursor = db.execute(
            "SELECT root_id, path, enabled, created_at FROM roots WHERE enabled = 1"
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def list_all(self) -> list[dict]:
        """List all roots."""
        db = get_db()
        cursor = db.execute(
            "SELECT root_id, path, enabled, created_at FROM roots"
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def set_enabled(self, root_id: str, enabled: bool) -> bool:
        """Enable or disable a root. Returns True if updated."""
        db = get_db()
        cursor = db.execute(
            "UPDATE roots SET enabled = ? WHERE root_id = ?",
            (int(enabled), root_id),
        )
        db.commit()
        return cursor.rowcount > 0
    
    def delete(self, root_id: str) -> bool:
        """Delete a root and its files. Returns True if deleted."""
        db = get_db()
        cursor = db.execute("DELETE FROM roots WHERE root_id = ?", (root_id,))
        db.commit()
        return cursor.rowcount > 0
