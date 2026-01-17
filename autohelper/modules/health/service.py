"""Health service - status checks and diagnostics."""

from datetime import UTC, datetime
from pathlib import Path

from autohelper import __version__
from autohelper.config import Settings, get_settings
from autohelper.db import get_db
from autohelper.db.migrate import get_migration_status

from .schemas import (
    HealthResponse,
    IndexStatus,
    MigrationStatus,
    RootStatus,
    StatusResponse,
)


class HealthService:
    """Service for health checks and status."""
    
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
    
    def get_health(self) -> HealthResponse:
        """Simple health check."""
        return HealthResponse(
            status="ok",
            timestamp=datetime.now(UTC),
            version=__version__,
        )
    
    def get_status(self) -> StatusResponse:
        """Full status with diagnostics."""
        db = get_db()
        
        # Check DB reachability
        db_reachable = False
        try:
            db.execute("SELECT 1")
            db_reachable = True
        except Exception:
            pass
        
        # Get migration status
        migration_status = MigrationStatus(applied_count=0, pending_count=0)
        if db_reachable:
            try:
                mig = get_migration_status(db)
                migration_status = MigrationStatus(
                    applied_count=mig["applied_count"],
                    pending_count=mig["pending_count"],
                )
            except Exception:
                pass
        
        # Get roots status
        roots: list[RootStatus] = []
        total_files = 0
        if db_reachable:
            try:
                cursor = db.execute("""
                    SELECT r.root_id, r.path, r.enabled,
                           (SELECT COUNT(*) FROM files f WHERE f.root_id = r.root_id) as file_count
                    FROM roots r
                """)
                for row in cursor.fetchall():
                    path = Path(row["path"])
                    roots.append(RootStatus(
                        root_id=row["root_id"],
                        path=row["path"],
                        enabled=bool(row["enabled"]),
                        accessible=path.exists() and path.is_dir(),
                        file_count=row["file_count"],
                    ))
                    total_files += row["file_count"]
            except Exception:
                pass
        
        # Get last index run
        index_status = IndexStatus(
            last_run_id=None,
            last_run_at=None,
            last_run_status=None,
            total_files=total_files,
            total_roots=len(roots),
        )
        if db_reachable:
            try:
                cursor = db.execute("""
                    SELECT index_run_id, started_at, status
                    FROM index_runs
                    ORDER BY started_at DESC
                    LIMIT 1
                """)
                row = cursor.fetchone()
                if row:
                    index_status.last_run_id = row["index_run_id"]
                    index_status.last_run_at = datetime.fromisoformat(row["started_at"])
                    index_status.last_run_status = row["status"]
            except Exception:
                pass
        
        return StatusResponse(
            status="ok" if db_reachable else "degraded",
            version=__version__,
            timestamp=datetime.now(UTC),
            debug=self._settings.debug,
            db_path=str(self._settings.db_path),
            db_reachable=db_reachable,
            migrations=migration_status,
            index=index_status,
            roots=roots,
        )
