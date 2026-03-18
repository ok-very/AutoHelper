"""
Reference service - traceability and resolution logic.
"""

import uuid
from datetime import datetime
from pathlib import Path

from autohelper.db import get_db
from autohelper.infra.audit import audit_operation
from autohelper.infra.fs.local_fs import local_fs
from autohelper.modules.index.service import IndexService
from autohelper.shared.errors import NotFoundError
from autohelper.shared.logging import get_logger, get_request_context

from .schemas import ReferenceCreate, ReferenceDTO, ResolutionResult

logger = get_logger(__name__)


class ReferenceService:
    """Service for managing file references."""

    def __init__(self) -> None:
        self.db = get_db()
        self.index_service = IndexService()

    @audit_operation("ref.register")
    def register(self, req: ReferenceCreate) -> ReferenceDTO:
        """
        Register a reference to a path.
        If file exists and is indexed, we link to file_id + content_hash.
        If not indexed, we try to index it first (lightweight).
        """
        from autohelper.shared.time import utcnow_iso

        # 1. Resolve path to canonical
        # Ensure path is absolute and resolved
        try:
            canonical_path = str(Path(req.path).resolve())
        except Exception as e:
            # If path is invalid, fail
            raise ValueError(f"Invalid path: {req.path}") from e

        # Check if file exists in index
        # Normalized path for lookup
        # Note: M0/M1 indexer stores normalized canonical paths.
        # We should use same normalization.

        # We need to find the file_id if it exists.
        # We can trigger a quick index of just this file if missing?

        # Check DB first
        # We need to support lookup by path.
        # Let's try flexible lookup (exact then case-insensitive)
        file_id = None
        content_hash = None

        row = self.db.execute(
            "SELECT file_id, content_hash FROM files WHERE canonical_path = ?", (canonical_path,)
        ).fetchone()
        if not row:
            row = self.db.execute(
                "SELECT file_id, content_hash FROM files WHERE lower(canonical_path) = lower(?)",
                (canonical_path,),
            ).fetchone()

        if row:
            file_id = row["file_id"]
            content_hash = row["content_hash"]
        else:
            # Not in index. Should we check disk?
            # For M3, let's just record the path. But better robustness if we have file_id.
            pass

        ref_id = str(uuid.uuid4())
        ctx = get_request_context()
        user = ctx.actor if ctx else "system"

        sql = """
            INSERT INTO refs (
                ref_id, work_item_id, context_id, 
                file_id, canonical_path, content_hash,
                created_at, created_by, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            ref_id,
            req.work_item_id or (ctx.work_item_id if ctx else None),
            req.context_id or (ctx.context_id if ctx else None),
            file_id,
            canonical_path,
            content_hash,
            utcnow_iso(),
            user,
            req.note,
        )
        self.db.execute(sql, params)
        self.db.commit()

        return self.get_ref(ref_id)

    def get_ref(self, ref_id: str) -> ReferenceDTO:
        """Get reference by ID."""
        row = self.db.execute("SELECT * FROM refs WHERE ref_id = ?", (ref_id,)).fetchone()
        if not row:
            raise NotFoundError(resource_type="ref", resource_id=ref_id)

        return ReferenceDTO(
            ref_id=row["ref_id"],
            file_id=row["file_id"],
            path=row["canonical_path"],
            # Check if broken? Simple status for now.
            status="active",  # TODO: check if file_id still exists or path exists
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    @audit_operation("ref.resolve")
    def resolve(self, ref_id: str) -> ResolutionResult:
        """
        Resolve a reference to a current path.

        Strategy:
        1. Exact path match (if file exists at recorded path).
        2. File ID match (if indexed file moved but ID tracked - assumes ID
           persistence which we don't fully have yet in M1 without inode
           tracking, but indexer cleans up missing files). Wait, M1 indexer
           deletes missing files. So `file_id` is lost if file moves! Unless
           we implement move detection in M1 (we didn't). So `file_id` match
           only works if file is stable.
        3. Content Hash match (if file moved but content is same).
        """
        ref = self.db.execute("SELECT * FROM refs WHERE ref_id = ?", (ref_id,)).fetchone()
        if not ref:
            raise NotFoundError(resource_type="ref", resource_id=ref_id)

        recorded_path = ref["canonical_path"]
        recorded_hash = ref["content_hash"]

        # 1. Exact Path Match
        # Check if file exists at path AND (optional) matches hash if we have one?
        # For speed, just check existence + maybe size/mtime from DB index.

        # Check live file system logic or DB index?
        # AutoHelper favors DB index as source of truth for "Managed" files.
        # But if file changed on disk and index didn't run, DB is stale.
        # Real-time verify? local_fs.exists(recorded_path)

        if local_fs.exists(Path(recorded_path)):
            # It's there.
            return ResolutionResult(
                ref_id=ref_id, found=True, path=recorded_path, confidence=1.0, strategy="exact"
            )

        # 2. Hash Match (The "Context Layer" magic)
        # File moved? Use content_hash to find it in `files` table.
        if recorded_hash:
            # Find files with same hash
            matches = self.db.execute(
                "SELECT canonical_path, file_id FROM files WHERE content_hash = ?", (recorded_hash,)
            ).fetchall()

            if matches:
                # Found proper move?
                # If multiple, picking first one or heuristic?
                # For now pick first.
                best_match = matches[0]

                # Self-healing: Update ref?
                # Spec says "Traceability model". Updating ref is good.
                # Let's not auto-update on GET, but maybe we should?
                # "AutoHelper" implies helping.
                # Let's just return the new path for now.

                return ResolutionResult(
                    ref_id=ref_id,
                    found=True,
                    path=best_match["canonical_path"],
                    confidence=0.9,  # High confidence cause hash match
                    strategy="hash",
                    file_info={"file_id": best_match["file_id"]},
                )

        return ResolutionResult(
            ref_id=ref_id, found=False, path=None, confidence=0.0, strategy="none"
        )
