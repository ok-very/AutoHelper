"""Repository for index run tracking."""

import json
from datetime import UTC, datetime

from autohelper.db import get_db
from autohelper.shared.ids import generate_index_run_id
from autohelper.shared.types import IndexRunStatus


class IndexRunRepository:
    """Track index run history and status."""
    
    def create(self, kind: str) -> str:
        """Create a new index run. Returns index_run_id."""
        db = get_db()
        run_id = generate_index_run_id()
        
        db.execute(
            "INSERT INTO index_runs (index_run_id, kind, status) VALUES (?, ?, ?)",
            (run_id, kind, IndexRunStatus.RUNNING.value),
        )
        db.commit()
        return run_id
    
    def complete(
        self,
        run_id: str,
        status: IndexRunStatus,
        stats: dict | None = None,
    ) -> None:
        """Mark run as complete with final status and stats."""
        db = get_db()
        now = datetime.now(UTC).isoformat()
        
        db.execute(
            """UPDATE index_runs SET 
                finished_at = ?, status = ?, stats_json = ?
            WHERE index_run_id = ?""",
            (now, status.value, json.dumps(stats) if stats else None, run_id),
        )
        db.commit()
    
    def _row_to_run(self, row: dict | None) -> dict | None:
        """Convert database row to run dict with parsed stats."""
        if not row:
            return None
        result = dict(row)
        if result.get("stats_json"):
            result["stats"] = json.loads(result["stats_json"])
        return result

    def get(self, run_id: str) -> dict | None:
        """Get index run by ID."""
        db = get_db()
        cursor = db.execute(
            "SELECT * FROM index_runs WHERE index_run_id = ?",
            (run_id,),
        )
        return self._row_to_run(cursor.fetchone())
    
    def get_latest(self, kind: str | None = None) -> dict | None:
        """Get most recent index run, optionally filtered by kind."""
        db = get_db()
        if kind:
            cursor = db.execute(
                """SELECT * FROM index_runs 
                WHERE kind = ? ORDER BY started_at DESC LIMIT 1""",
                (kind,),
            )
        else:
            cursor = db.execute(
                "SELECT * FROM index_runs ORDER BY started_at DESC LIMIT 1"
            )
        return self._row_to_run(cursor.fetchone())

    def get_last_completed(self, kind: str | None = None) -> dict | None:
        """Get most recent completed index run, optionally filtered by kind."""
        db = get_db()
        if kind:
            cursor = db.execute(
                """SELECT * FROM index_runs 
                WHERE status = ? AND kind = ? 
                ORDER BY finished_at DESC, started_at DESC LIMIT 1""",
                (IndexRunStatus.COMPLETED.value, kind),
            )
        else:
            cursor = db.execute(
                """SELECT * FROM index_runs 
                WHERE status = ? 
                ORDER BY finished_at DESC, started_at DESC LIMIT 1""",
                (IndexRunStatus.COMPLETED.value,),
            )
        return self._row_to_run(cursor.fetchone())
    
    def get_running(self) -> dict | None:
        """Get currently running index run if any."""
        db = get_db()
        cursor = db.execute(
            "SELECT * FROM index_runs WHERE status = ? LIMIT 1",
            (IndexRunStatus.RUNNING.value,),
        )
        return self._row_to_run(cursor.fetchone())
    
    def cancel_stale(self, older_than_minutes: int = 60) -> int:
        """Cancel runs that have been running too long."""
        db = get_db()
        cutoff = datetime.now(UTC).isoformat()
        
        cursor = db.execute(
            """UPDATE index_runs SET status = ?, finished_at = ?
            WHERE status = ? 
            AND datetime(started_at) < datetime(?, '-' || ? || ' minutes')""",
            (IndexRunStatus.CANCELLED.value, cutoff,
             IndexRunStatus.RUNNING.value, cutoff, older_than_minutes),
        )
        db.commit()
        return cursor.rowcount
