"""
Simple migration runner using schema_migrations table.
"""

import re
from pathlib import Path
from typing import Any

from autohelper.shared.logging import get_logger

from .conn import Database

logger = get_logger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

# Schema for tracking applied migrations
MIGRATION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""


def get_applied_migrations(db: Database) -> set[str]:
    """Get set of applied migration versions."""
    db.execute(MIGRATION_TABLE_SQL)
    db.commit()

    cursor = db.execute("SELECT version FROM schema_migrations ORDER BY version")
    return {row["version"] for row in cursor.fetchall()}


def get_pending_migrations(db: Database) -> list[tuple[str, str]]:
    """
    Get list of pending migrations as (version, sql) tuples.
    Sorted by version number.
    """
    applied = get_applied_migrations(db)
    pending: list[tuple[str, str]] = []

    if not MIGRATIONS_DIR.exists():
        logger.warning(f"Migrations directory not found: {MIGRATIONS_DIR}")
        return pending

    for migration_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        # Extract version from filename (e.g., "0001_init.sql" -> "0001")
        match = re.match(r"^(\d+)", migration_file.name)
        if match:
            version = match.group(1)
            if version not in applied:
                sql = migration_file.read_text(encoding="utf-8")
                pending.append((version, sql))

    return pending


def run_migrations(db: Database) -> list[str]:
    """
    Run all pending migrations.

    Returns:
        List of applied migration versions
    """
    pending = get_pending_migrations(db)
    applied: list[str] = []

    for version, sql in pending:
        logger.info(f"Applying migration {version}")
        try:
            # Execute migration (may contain multiple statements)
            db.connect().executescript(sql)

            # Record migration
            db.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
            db.commit()
            applied.append(version)
            logger.info(f"Applied migration {version}")
        except Exception as e:
            db.rollback()
            logger.error(f"Migration {version} failed: {e}")
            raise

    return applied


def get_migration_status(db: Database) -> dict[str, Any]:
    """Get migration status summary."""
    applied = get_applied_migrations(db)
    pending = get_pending_migrations(db)

    return {
        "applied_count": len(applied),
        "pending_count": len(pending),
        "applied_versions": sorted(applied),
        "pending_versions": [v for v, _ in pending],
    }
