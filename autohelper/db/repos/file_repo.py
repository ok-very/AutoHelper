"""Repository for file index operations."""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from autohelper.db import get_db
from autohelper.shared.ids import generate_file_id


class FileRepository:
    """CRUD operations for files table with memory-efficient batching."""

    def upsert(
        self,
        root_id: str,
        canonical_path: str,
        rel_path: str,
        size: int,
        mtime_ns: int,
        is_dir: bool,
        ext: str,
        content_hash: str | None = None,
        mime: str | None = None,
    ) -> str:
        """Insert or update a file entry. Returns file_id."""
        db = get_db()
        now = datetime.now(UTC).isoformat()

        # Check if exists
        cursor = db.execute(
            "SELECT file_id FROM files WHERE canonical_path = ?",
            (canonical_path,),
        )
        row = cursor.fetchone()

        if row:
            # Update existing
            file_id: str = row["file_id"]
            db.execute(
                """UPDATE files SET
                    root_id = ?, rel_path = ?, size = ?, mtime_ns = ?,
                    content_hash = ?, is_dir = ?, ext = ?, mime = ?,
                    last_seen_at = ?
                WHERE file_id = ?""",
                (
                    root_id,
                    rel_path,
                    size,
                    mtime_ns,
                    content_hash,
                    int(is_dir),
                    ext,
                    mime,
                    now,
                    file_id,
                ),
            )
        else:
            # Insert new
            file_id = generate_file_id()
            db.execute(
                """INSERT INTO files 
                    (file_id, root_id, canonical_path, rel_path, size, mtime_ns,
                     content_hash, indexed_at, last_seen_at, is_dir, ext, mime)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    file_id,
                    root_id,
                    canonical_path,
                    rel_path,
                    size,
                    mtime_ns,
                    content_hash,
                    now,
                    now,
                    int(is_dir),
                    ext,
                    mime,
                ),
            )

        db.commit()
        return file_id

    def upsert_batch(self, files: list[dict[str, Any]]) -> int:
        """
        Batch upsert files. Memory-efficient for large crawls.

        Args:
            files: List of dicts with keys matching upsert() params

        Returns:
            Number of files processed
        """
        if not files:
            return 0

        db = get_db()
        now = datetime.now(UTC).isoformat()
        count = 0

        # Prefetch existing file_ids in batches to avoid N+1 queries
        # SQLite default limit is 999 params, use 500 for safety
        all_paths = [f["canonical_path"] for f in files]
        existing_map: dict[str, str] = {}
        batch_size = 500

        for i in range(0, len(all_paths), batch_size):
            batch_paths = all_paths[i : i + batch_size]
            placeholders = ",".join("?" * len(batch_paths))
            cursor = db.execute(
                f"SELECT canonical_path, file_id FROM files WHERE canonical_path IN ({placeholders})",
                tuple(batch_paths),
            )
            for row in cursor:
                existing_map[row["canonical_path"]] = row["file_id"]

        for file_data in files:
            canonical_path = file_data["canonical_path"]
            file_id = existing_map.get(canonical_path)

            if file_id:
                db.execute(
                    """UPDATE files SET
                        root_id = ?, rel_path = ?, size = ?, mtime_ns = ?,
                        content_hash = ?, is_dir = ?, ext = ?, mime = ?,
                        last_seen_at = ?
                    WHERE file_id = ?""",
                    (
                        file_data["root_id"],
                        file_data["rel_path"],
                        file_data["size"],
                        file_data["mtime_ns"],
                        file_data.get("content_hash"),
                        int(file_data["is_dir"]),
                        file_data["ext"],
                        file_data.get("mime"),
                        now,
                        file_id,
                    ),
                )
            else:
                file_id = generate_file_id()
                db.execute(
                    """INSERT INTO files 
                        (file_id, root_id, canonical_path, rel_path, size, mtime_ns,
                         content_hash, indexed_at, last_seen_at, is_dir, ext, mime)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        file_id,
                        file_data["root_id"],
                        canonical_path,
                        file_data["rel_path"],
                        file_data["size"],
                        file_data["mtime_ns"],
                        file_data.get("content_hash"),
                        now,
                        now,
                        int(file_data["is_dir"]),
                        file_data["ext"],
                        file_data.get("mime"),
                    ),
                )
            count += 1

        db.commit()
        return count

    def get_by_path(self, canonical_path: str) -> dict[str, Any] | None:
        """Get file by canonical path."""
        db = get_db()
        cursor = db.execute(
            "SELECT * FROM files WHERE canonical_path = ?",
            (canonical_path,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_by_root(self, root_id: str) -> Iterator[dict[str, Any]]:
        """Stream files for a root (memory-efficient generator)."""
        db = get_db()
        cursor = db.execute(
            "SELECT * FROM files WHERE root_id = ?",
            (root_id,),
        )
        while row := cursor.fetchone():
            yield dict(row)

    def get_file_stats(self, root_id: str) -> dict[str, Any]:
        """Get quick stats for a root without loading all files."""
        db = get_db()
        cursor = db.execute(
            """SELECT 
                COUNT(*) as total_files,
                SUM(CASE WHEN is_dir = 0 THEN 1 ELSE 0 END) as file_count,
                SUM(CASE WHEN is_dir = 1 THEN 1 ELSE 0 END) as dir_count,
                SUM(size) as total_size
            FROM files WHERE root_id = ?""",
            (root_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else {}

    def purge_missing(self, root_id: str, seen_before: str) -> int:
        """
        Permanently delete files not seen since timestamp.

        This is a destructive operation - files are hard-deleted from the database.
        Use with caution. For soft-delete behavior, consider adding a 'deleted_at'
        column in a future migration.

        Args:
            root_id: The root to purge files from
            seen_before: ISO timestamp - files with last_seen_at before this are deleted

        Returns:
            Count of files deleted
        """
        db = get_db()
        cursor = db.execute(
            "DELETE FROM files WHERE root_id = ? AND last_seen_at < ?",
            (root_id, seen_before),
        )
        db.commit()
        return cursor.rowcount

    def get_changed_since(self, root_id: str, since: str) -> Iterator[dict[str, Any]]:
        """Stream files changed since timestamp."""
        db = get_db()
        cursor = db.execute(
            "SELECT * FROM files WHERE root_id = ? AND last_seen_at > ?",
            (root_id, since),
        )
        while row := cursor.fetchone():
            yield dict(row)

    def count_by_root(self, root_id: str) -> int:
        """Count files in a root."""
        db = get_db()
        cursor = db.execute(
            "SELECT COUNT(*) as cnt FROM files WHERE root_id = ?",
            (root_id,),
        )
        row = cursor.fetchone()
        return int(row["cnt"]) if row else 0
