"""
Search service - search logic.
"""

import time

from autohelper.db import get_db
from autohelper.infra.audit import audit_operation
from autohelper.shared.logging import get_logger

from .schemas import FileResult, SearchResponse

logger = get_logger(__name__)


class SearchService:
    """Service for searching indexed files."""

    def __init__(self) -> None:
        self.db = get_db()

    @audit_operation("search.query")
    def search(self, query: str, limit: int = 50) -> SearchResponse:
        """
        Search files by name/path.
        Includes matches from file_aliases (old names).

        Args:
            query: Search string
            limit: Max results

        Returns:
            SearchResponse
        """
        start_time = time.time()

        # Simple LIKE query for M2 + Alias Support
        wildcard = f"%{query}%"

        # 1. Main Search (Files)
        sql_files = """
            SELECT 
                file_id, 
                root_id, 
                canonical_path as path, 
                size, 
                mtime_ns as mtime, 
                is_dir,
                NULL as matched_alias
            FROM files
            WHERE rel_path LIKE ? OR canonical_path LIKE ?
            ORDER BY is_dir DESC, last_seen_at DESC
            LIMIT ?
        """

        # 2. Alias Search
        # If we didn't fill the limit, look for aliases
        # Or UNION them? UNION is cleaner but limits applied after.
        # Let's do two queries for better control/relevance, or a UNION.
        # UNION ALL allows duplicates if file matches both (unlikely for exact string).
        # But if I search "foo", and file is "foo.txt" (old: "foo_old.txt"), both match.
        # We should deduplicate by file_id.

        sql = """
            SELECT 
                f.file_id, 
                f.root_id, 
                f.canonical_path as path, 
                f.size, 
                f.mtime_ns as mtime, 
                f.is_dir,
                fa.old_canonical_path as matched_alias
            FROM file_aliases fa
            JOIN files f ON fa.file_id = f.file_id
            WHERE fa.old_canonical_path LIKE ?
            LIMIT ?
        """

        # Execute File Search
        cursor = self.db.execute(sql_files, (wildcard, wildcard, limit))
        results_map = {}  # file_id -> item

        for row in cursor.fetchall():
            results_map[row["file_id"]] = FileResult(
                file_id=row["file_id"],
                path=row["path"],
                root_id=row["root_id"],
                size=row["size"],
                mtime=row["mtime"],
                is_dir=bool(row["is_dir"]),
            )

        # Execute Alias Search (if we need more or want completeness)
        # Assuming we want to show aliases even if primary matches exist
        remaining = limit - len(results_map)
        if remaining > 0:
            cursor_aliases = self.db.execute(sql, (wildcard, remaining))
            for row in cursor_aliases.fetchall():
                if row["file_id"] not in results_map:
                    # Found via alias
                    item = FileResult(
                        file_id=row["file_id"],
                        path=row["path"],
                        root_id=row["root_id"],
                        size=row["size"],
                        mtime=row["mtime"],
                        is_dir=bool(row["is_dir"]),
                        matched_alias=True,
                        alias_of=row["matched_alias"],
                    )
                    results_map[row["file_id"]] = item

        items = list(results_map.values())

        took_ms = int((time.time() - start_time) * 1000)

        return SearchResponse(items=items, total=len(items), took_ms=took_ms)
