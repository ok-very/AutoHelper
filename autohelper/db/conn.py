"""
SQLite connection factory with WAL mode and pragmas.
"""

import sqlite3
from pathlib import Path
from typing import Any

# Connection settings for performance and safety
PRAGMAS = [
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA foreign_keys=ON",
    "PRAGMA busy_timeout=5000",
    "PRAGMA cache_size=-64000",  # 64MB cache
]


def get_connection(db_path: Path) -> sqlite3.Connection:
    """
    Create a new SQLite connection with optimal settings.
    
    Note: Each connection should be used by a single thread.
    For async, use aiosqlite which wraps this.
    """
    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    
    # Apply pragmas
    for pragma in PRAGMAS:
        conn.execute(pragma)
    
    return conn


class Database:
    """Database wrapper with connection management."""
    
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
    
    @property
    def path(self) -> Path:
        return self._db_path
    
    def connect(self) -> sqlite3.Connection:
        """Get or create connection."""
        if self._conn is None:
            self._conn = get_connection(self._db_path)
        return self._conn
    
    def close(self) -> None:
        """Close connection if open."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
    
    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        """Execute SQL and return cursor."""
        return self.connect().execute(sql, params)
    
    def executemany(self, sql: str, params_list: list[tuple[Any, ...]]) -> sqlite3.Cursor:
        """Execute SQL for multiple parameter sets."""
        return self.connect().executemany(sql, params_list)
    
    def commit(self) -> None:
        """Commit current transaction."""
        if self._conn:
            self._conn.commit()
    
    def rollback(self) -> None:
        """Rollback current transaction."""
        if self._conn:
            self._conn.rollback()


# Global database instance (set during app startup)
_db: Database | None = None


def init_db(db_path: Path) -> Database:
    """Initialize the global database instance."""
    global _db
    _db = Database(db_path)
    return _db


def get_db() -> Database:
    """Get the global database instance."""
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _db
