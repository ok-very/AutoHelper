"""
Index service - memory-efficient filesystem crawling.
Uses generators and batched writes to handle large directories.
"""

import os
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

from autohelper.config import get_settings
from autohelper.db.repos import FileRepository, IndexRunRepository, RootRepository
from autohelper.infra.fs.hashing import hasher
from autohelper.shared.errors import ConflictError
from autohelper.shared.logging import get_logger
from autohelper.shared.types import IndexRunStatus

logger = get_logger(__name__)

# Process files in batches to limit memory
BATCH_SIZE = 500
# Default max file size for hashing (100MB)
DEFAULT_MAX_HASH_SIZE = 100 * 1024 * 1024


class IndexService:
    """
    Filesystem indexing with memory-efficient streaming.
    
    Key memory optimizations:
    - Generator-based file walking (no full list in memory)
    - Batched database writes
    - Streaming hash computation
    """
    
    def __init__(self) -> None:
        self._file_repo = FileRepository()
        self._root_repo = RootRepository()
        self._run_repo = IndexRunRepository()
        self._settings = get_settings()
    
    def _walk_directory(
        self,
        root_path: Path,
        root_id: str,
        include_hash: bool = False,
        max_hash_size: int = DEFAULT_MAX_HASH_SIZE,
    ) -> Generator[dict, None, None]:
        """
        Memory-efficient directory walker using os.scandir.
        Yields file metadata dicts.
        """
        # Use os.walk with scandir for memory efficiency
        for dirpath, _dirnames, filenames in os.walk(root_path, onerror=lambda e: None):
            current = Path(dirpath)
            
            # Skip symlinks if policy blocks them
            if self._settings.block_symlinks and current.is_symlink():
                continue
            
            # Yield directory entry
            try:
                rel_path = str(current.relative_to(root_path))
                if rel_path == ".":
                    rel_path = ""
                
                stat = current.stat()
                yield {
                    "root_id": root_id,
                    "canonical_path": str(current),
                    "rel_path": rel_path,
                    "size": 0,
                    "mtime_ns": stat.st_mtime_ns,
                    "is_dir": True,
                    "ext": "",
                    "content_hash": None,
                }
            except OSError as e:
                logger.debug(f"Error reading dir {current}: {e}")
            
            # Yield file entries
            for filename in filenames:
                file_path = current / filename
                
                # Skip symlinks
                if self._settings.block_symlinks and file_path.is_symlink():
                    continue
                
                try:
                    stat = file_path.stat()
                    ext = file_path.suffix.lower().lstrip(".")
                    
                    # Compute hash if requested and file is small enough
                    content_hash = None
                    if include_hash and stat.st_size <= max_hash_size:
                        content_hash = hasher.hash_file(file_path, max_hash_size)
                    
                    yield {
                        "root_id": root_id,
                        "canonical_path": str(file_path),
                        "rel_path": str(file_path.relative_to(root_path)),
                        "size": stat.st_size,
                        "mtime_ns": stat.st_mtime_ns,
                        "is_dir": False,
                        "ext": ext,
                        "content_hash": content_hash,
                    }
                except OSError as e:
                    logger.debug(f"Error reading file {file_path}: {e}")
    
    def rebuild(
        self,
        root_ids: list[str] | None = None,
        include_hash: bool = False,
        max_hash_size: int = DEFAULT_MAX_HASH_SIZE,
    ) -> dict:
        """
        Full index rebuild with memory-efficient batching.
        
        Args:
            root_ids: Specific roots to rebuild, or all if None
            include_hash: Compute content hashes
            max_hash_size: Max file size for hashing (bytes)
        
        Returns:
            Stats dict with counts and timing
        """
        # Check for running index
        running = self._run_repo.get_running()
        if running:
            raise ConflictError(
                message=f"Index already running: {running['index_run_id']}",
                details={"running_id": running["index_run_id"]},
            )
        
        # Create index run
        run_id = self._run_repo.create(kind="full")
        logger.info(f"Starting full rebuild: {run_id}")
        
        start_time = datetime.now(UTC)
        scan_start = start_time.isoformat()
        
        # Get roots to process
        if root_ids:
            roots = []
            for rid in root_ids:
                root = self._root_repo.get_by_id(rid)
                if root is not None:
                    roots.append(root)
        else:
            roots = self._root_repo.list_enabled()
        
        # Also add configured roots not yet in DB
        for root_path in self._settings.get_allowed_roots():
            root_id, created = self._root_repo.get_or_create(root_path)
            if created:
                roots.append({"root_id": root_id, "path": str(root_path)})
        
        total_files = 0
        total_dirs = 0
        roots_processed = 0
        
        try:
            for root in roots:
                root_path = Path(root["path"])
                root_id = root["root_id"]
                
                if not root_path.exists():
                    logger.warning(f"Root not accessible: {root_path}")
                    continue
                
                logger.info(f"Indexing root: {root_path}")
                
                # Process in batches
                batch: list[dict] = []
                walker = self._walk_directory(
                    root_path, root_id, include_hash, max_hash_size
                )
                
                for file_data in walker:
                    batch.append(file_data)
                    
                    if len(batch) >= BATCH_SIZE:
                        self._file_repo.upsert_batch(batch)
                        total_files += len([f for f in batch if not f["is_dir"]])
                        total_dirs += len([f for f in batch if f["is_dir"]])
                        batch = []
                
                # Process remaining batch
                if batch:
                    self._file_repo.upsert_batch(batch)
                    total_files += len([f for f in batch if not f["is_dir"]])
                    total_dirs += len([f for f in batch if f["is_dir"]])
                
                # Clean up files not seen in this scan
                removed = self._file_repo.mark_missing(root_id, scan_start)
                logger.info(f"Removed {removed} stale entries from {root_path}")
                
                roots_processed += 1
            
            # Complete run successfully
            elapsed = (datetime.now(UTC) - start_time).total_seconds()
            stats = {
                "roots_processed": roots_processed,
                "files_indexed": total_files,
                "dirs_indexed": total_dirs,
                "elapsed_seconds": elapsed,
            }
            
            self._run_repo.complete(run_id, IndexRunStatus.COMPLETED, stats)
            logger.info(f"Rebuild complete: {stats}")
            
            return {"index_run_id": run_id, "status": "completed", **stats}
            
        except Exception as e:
            logger.error(f"Rebuild failed: {e}")
            self._run_repo.complete(
                run_id,
                IndexRunStatus.FAILED,
                {"error": str(e)},
            )
            raise
    
    def rescan(self, root_ids: list[str] | None = None) -> dict:
        """
        Incremental rescan - only check changed files.
        Uses stat comparison (size + mtime) for efficiency.
        """
        # For now, rescan is same as rebuild but could be optimized
        # to only stat files and compare, skipping unchanged
        return self.rebuild(root_ids=root_ids, include_hash=False)
    
    def get_status(self) -> dict:
        """Get current index status."""
        running = self._run_repo.get_running()
        last_completed = self._run_repo.get_last_completed()
        roots = self._root_repo.list_all()
        
        total_files = sum(
            self._file_repo.count_by_root(r["root_id"])
            for r in roots
        )
        
        return {
            "is_running": running is not None,
            "current_run": running,
            "last_completed": last_completed,
            "total_roots": len(roots),
            "total_files": total_files,
        }
    
    def get_root_stats(self) -> list[dict]:
        """Get per-root statistics."""
        roots = self._root_repo.list_all()
        result = []
        
        for root in roots:
            stats = self._file_repo.get_file_stats(root["root_id"])
            result.append({
                "root_id": root["root_id"],
                "path": root["path"],
                "file_count": stats.get("file_count", 0) or 0,
                "dir_count": stats.get("dir_count", 0) or 0,
                "total_size": stats.get("total_size", 0) or 0,
            })
        
        return result
