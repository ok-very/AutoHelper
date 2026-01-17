"""
Index service - core crawling logic.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autohelper.config import get_settings
from autohelper.db import get_db
from autohelper.infra.fs.local_fs import local_fs
from autohelper.infra.fs.path_policy import PathPolicy
from autohelper.infra.fs.hashing import hasher
from autohelper.shared.errors import NotFoundError
from autohelper.shared.ids import generate_file_id, generate_index_run_id
from autohelper.shared.logging import get_logger
from autohelper.infra.audit import audit_operation
from autohelper.shared.types import IndexRunStatus, RequestContext

from .schemas import IndexStats, RunResponse
from .types import ScanResult

logger = get_logger(__name__)


def utcnow_iso() -> str:
    """Get current UTC time in ISO format."""
    return datetime.now(timezone.utc).isoformat()


class IndexService:
    """Service for indexing filesystem roots."""
    
    def __init__(self) -> None:
        self.settings = get_settings()
        self.db = get_db()
        self.fs = local_fs
        # Policy is needed to resolve roots
        self.policy = PathPolicy(self.settings.get_allowed_roots(), self.settings.block_symlinks)

    @audit_operation("index.rebuild")
    def rebuild_index(self, specific_root_id: str | None = None, force_hash: bool = False) -> RunResponse:
        """
        Trigger a full index rebuild.
        
        Note: In a real async implementation, this would kick off a background task.
        For M0/M1 MVP, we run synchronously but still track it as a 'run'.
        """
        run_id = generate_index_run_id()
        start_time = time.time()
        
        # 1. Create run record
        self.db.execute(
            """
            INSERT INTO index_runs (index_run_id, kind, started_at, status)
            VALUES (?, ?, ?, ?)
            """,
            (run_id, "full", utcnow_iso(), IndexRunStatus.RUNNING)
        )
        self.db.commit()
        
        try:
            # 2. Determine roots to scan
            roots_to_scan = []
            if specific_root_id:
                # Validate root exists in DB
                row = self.db.execute(
                    "SELECT root_id, path FROM roots WHERE root_id = ?", 
                    (specific_root_id,)
                ).fetchone()
                if not row:
                    raise NotFoundError(resource_type="root", resource_id=specific_root_id)
                roots_to_scan.append((row["root_id"], Path(row["path"])))
            else:
                # Scan all enabled roots
                # First ensure DB has all configured roots
                self._sync_configured_roots()
                
                cursor = self.db.execute("SELECT root_id, path FROM roots WHERE enabled = 1")
                for row in cursor.fetchall():
                    roots_to_scan.append((row["root_id"], Path(row["path"])))
            
            # 3. Perform scan
            total_stats = ScanResult()
            
            for root_id, root_path in roots_to_scan:
                logger.info(f"Scanning root {root_id}: {root_path}")
                stats = self._scan_root(root_id, root_path, force_hash)
                
                # Update total stats
                total_stats.added += stats.added
                total_stats.updated += stats.updated
                total_stats.removed += stats.removed
                total_stats.errors += stats.errors
                total_stats.total_size += stats.total_size
                
                # Update root status
                self.db.execute(
                    """
                    INSERT INTO index_state (root_id, last_full_scan_at)
                    VALUES (?, ?)
                    ON CONFLICT(root_id) DO UPDATE SET last_full_scan_at = excluded.last_full_scan_at
                    """,
                    (root_id, utcnow_iso())
                )
                self.db.commit()
            
            total_stats.duration_ms = int((time.time() - start_time) * 1000)
            
            # 4. Finish run
            self.db.execute(
                """
                UPDATE index_runs 
                SET status = ?, finished_at = ?, stats_json = ?
                WHERE index_run_id = ?
                """,
                (
                    IndexRunStatus.COMPLETED,
                    utcnow_iso(),
                    json.dumps(vars(total_stats)),
                    run_id
                )
            )
            self.db.commit()
            
            return RunResponse(
                run_id=run_id,
                status=IndexRunStatus.COMPLETED,
                started_at=datetime.fromtimestamp(start_time, timezone.utc),
            )
            
        except Exception as e:
            logger.error(f"Index run failed: {e}", exc_info=True)
            self.db.execute(
                """
                UPDATE index_runs 
                SET status = ?, finished_at = ?, stats_json = ?
                WHERE index_run_id = ?
                """,
                (
                    IndexRunStatus.FAILED,
                    utcnow_iso(),
                    json.dumps({"error": str(e)}),
                    run_id
                )
            )
            self.db.commit()
            raise

    def rescan(self) -> RunResponse:
        """Rescan all roots (alias for rebuild in M0/M1)."""
        # In future, rescan might be lighter than rebuild
        return self.rebuild_index()

    def get_status(self) -> dict[str, Any]:
        """Get current indexer status."""
        # Check if running
        running = self.db.execute(
            "SELECT * FROM index_runs WHERE status = ?", 
            (IndexRunStatus.RUNNING,)
        ).fetchone()
        
        # Last completed
        last_completed = self.db.execute(
            "SELECT * FROM index_runs WHERE status = ? ORDER BY finished_at DESC LIMIT 1",
            (IndexRunStatus.COMPLETED,)
        ).fetchone()
        
        # Total counts
        try:
            total_files = self.db.execute("SELECT count(*) as c FROM files").fetchone()["c"]
            total_roots = self.db.execute("SELECT count(*) as c FROM roots").fetchone()["c"]
        except Exception:
            total_files = 0
            total_roots = 0
        
        return {
            "is_running": bool(running),
            "current_run": dict(running) if running else None,
            "last_completed": dict(last_completed) if last_completed else None,
            "total_files": total_files,
            "total_roots": total_roots,
        }

    def get_roots_stats(self) -> list[dict[str, Any]]:
        """Get statistics per root."""
        # Join roots with files aggregate
        cursor = self.db.execute(
            """
            SELECT r.root_id, r.path, 
                   count(f.file_id) as file_count,
                   sum(case when f.is_dir = 1 then 1 else 0 end) as dir_count,
                   coalesce(sum(f.size), 0) as total_size
            FROM roots r
            LEFT JOIN files f ON r.root_id = f.root_id
            WHERE r.enabled = 1
            GROUP BY r.root_id
            """
        )
        return [dict(row) for row in cursor.fetchall()]

    def _sync_configured_roots(self) -> None:
        """Ensure all roots from settings are present in DB."""
        # This is a simple sync: add missing, disable removed
        # In a real system, we might want more complex logic
        
        current_config_paths = {str(p): p for p in self.policy.roots}
        
        # 1. Add new roots
        for path_str, path_obj in current_config_paths.items():
            # Check if exists (by path)
            row = self.db.execute("SELECT root_id FROM roots WHERE path = ?", (path_str,)).fetchone()
            if not row:
                from autohelper.shared.ids import generate_root_id
                root_id = generate_root_id()
                self.db.execute(
                    "INSERT INTO roots (root_id, path, enabled) VALUES (?, ?, 1)",
                    (root_id, path_str)
                )
                logger.info(f"Registered new root: {path_str}")
        
        self.db.commit()

    def _scan_root(self, root_id: str, root_path: Path, force_hash: bool) -> ScanResult:
        """Scan a single root directory."""
        stats = ScanResult()
        
        # Pre-load existing files for this root to detect deletions/changes
        # Using a dict for faster lookups: relative_path -> metadata
        existing_files = {}
        cursor = self.db.execute(
            """
            SELECT file_id, rel_path, mtime_ns, size, content_hash 
            FROM files 
            WHERE root_id = ?
            """,
            (root_id,)
        )
        for row in cursor.fetchall():
            existing_files[row["rel_path"]] = dict(row)
        
        seen_rel_paths = set()
        
        # Walk filesystem
        try:
            # We use os.walk/iterdir via local_fs abstraction if possible, 
            # but for performance recursive walk is best done directly or via simplified walker
            # Here we follow a simple recursive approach using local_fs.walk if available or os.walk
            
            # Simple recursive walk since local_fs.walk returns EVERYTHING and might be huge
            # Let's iterate carefully.
            
            for parent, dirs, files in self.fs.walk(root_path):
                # Filter dirs? (e.g. .git) - skipping hidden dirs for now
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                for filename in files:
                    if filename.startswith('.'):
                        continue
                        
                    file_path = parent / filename
                    try:
                        rel_path = str(file_path.relative_to(root_path))
                        seen_rel_paths.add(rel_path)
                        
                        file_stat = self.fs.stat(file_path)
                        stats.total_size += file_stat.size
                        
                        # Check against existing
                        existing = existing_files.get(rel_path)
                        
                        if existing:
                            # Update logic: check mtime/size
                            if (not force_hash and 
                                existing["size"] == file_stat.size and 
                                existing["mtime_ns"] == file_stat.mtime_ns):
                                # No change
                                # Update last_seen_at
                                self.db.execute(
                                    "UPDATE files SET last_seen_at = ? WHERE file_id = ?",
                                    (utcnow_iso(), existing["file_id"])
                                )
                                continue
                            
                            # Changed
                            self._upsert_file(root_id, root_path, rel_path, file_stat, existing["file_id"], force_hash)
                            stats.updated += 1
                        else:
                            # New file
                            self._upsert_file(root_id, root_path, rel_path, file_stat, None, force_hash)
                            stats.added += 1
                            
                    except Exception as e:
                        logger.warning(f"Error scanning file {file_path}: {e}")
                        stats.errors += 1
                        
                # Commit batch every so often? For now rely on sqlite speed
            
            self.db.commit()
            
            # Handle deletions
            for rel_path, info in existing_files.items():
                if rel_path not in seen_rel_paths:
                    # File is gone
                    self.db.execute("DELETE FROM files WHERE file_id = ?", (info["file_id"],))
                    stats.removed += 1
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to scan root {root_path}: {e}")
            stats.errors += 1
            
        return stats

    def _upsert_file(
        self, 
        root_id: str, 
        root_path: Path, 
        rel_path: str, 
        stat: Any, 
        existing_id: str | None,
        force_hash: bool
    ) -> None:
        """Insert or update a file record."""
        canonical_path = str(root_path / rel_path)
        
        # Calculate hash if needed
        # Policy: < 10MB always hash? Or only if requested?
        # M1 spec: "Keep hashing optional for now; add in incremental issue"
        # I will hash if force_hash is True OR if it's small (<1MB) to be helpful
        content_hash = None
        if force_hash or stat.size < 1_000_000:  # 1MB
            try:
                content_hash = hasher.hash_file(root_path / rel_path)
            except Exception:
                pass
        
        if existing_id:
            # Update
            self.db.execute(
                """
                UPDATE files 
                SET size = ?, mtime_ns = ?, content_hash = ?, 
                    last_seen_at = ?, indexed_at = ?, mime = ?
                WHERE file_id = ?
                """,
                (
                    stat.size,
                    stat.mtime_ns,
                    content_hash,
                    utcnow_iso(),
                    utcnow_iso(),
                    None, # Mime detection later
                    existing_id
                )
            )
        else:
            # Insert
            file_id = generate_file_id()
            self.db.execute(
                """
                INSERT INTO files (
                    file_id, root_id, canonical_path, rel_path,
                    size, mtime_ns, content_hash,
                    indexed_at, last_seen_at, is_dir, ext
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_id,
                    root_id,
                    canonical_path,
                    rel_path,
                    stat.size,
                    stat.mtime_ns,
                    content_hash,
                    utcnow_iso(),
                    utcnow_iso(),
                    0, # is_dir=False for files
                    Path(canonical_path).suffix.lower()
                )
            )
