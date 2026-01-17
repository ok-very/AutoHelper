"""
Search service - search logic.
"""

import time
from typing import Any

from autohelper.db import get_db
from autohelper.shared.logging import get_logger
from autohelper.infra.audit import audit_operation
from .schemas import SearchResponse, FileResult

logger = get_logger(__name__)


class SearchService:
    """Service for searching indexed files."""
    
    def __init__(self) -> None:
        self.db = get_db()

    @audit_operation("search.query")
    def search(self, query: str, limit: int = 50) -> SearchResponse:
        """
        Search files by name/path.
        
        Args:
            query: Search string
            limit: Max results
            
        Returns:
            SearchResponse
        """
        start_time = time.time()
        
        # Simple LIKE query for M2
        # Use %query% for path match
        sql = """
            SELECT file_id, root_id, canonical_path as path, size, mtime_ns as mtime, is_dir
            FROM files
            WHERE rel_path LIKE ? OR canonical_path LIKE ?
            ORDER BY is_dir DESC, last_seen_at DESC
            LIMIT ?
        """
        wildcard = f"%{query}%"
        
        cursor = self.db.execute(sql, (wildcard, wildcard, limit))
        items = []
        for row in cursor.fetchall():
            items.append(FileResult(
                file_id=row["file_id"],
                path=row["path"],
                root_id=row["root_id"],
                size=row["size"],
                mtime=row["mtime"],
                is_dir=bool(row["is_dir"])
            ))
            
        took_ms = int((time.time() - start_time) * 1000)
        
        return SearchResponse(
            items=items,
            total=len(items), # Total available match count is expensive, just return count of items
            took_ms=took_ms
        )
