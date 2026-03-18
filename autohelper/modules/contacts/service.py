"""Contact Sync service - orchestrates CSV read, diff, and sync."""

import json
import logging
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from autohelper.config import get_settings
from autohelper.db import get_db

from .csv_reader import file_hash, read_contacts_csv
from .types import ContactRecord, SyncResult

logger = logging.getLogger(__name__)


class ContactSyncService:
    """
    Singleton service for contact synchronization.

    Reads master CSV, detects changes via file hash + per-row hash,
    and delegates actual Exchange operations to exchange_sync module.
    """

    _instance: "ContactSyncService | None" = None
    _lock = threading.Lock()
    _initialized: bool = False

    def __new__(cls) -> "ContactSyncService":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self._last_result: SyncResult | None = None
        self._last_sync: datetime | None = None
        self._running = False
        self._run_lock = threading.Lock()
        self._initialized = True

    @property
    def is_running(self) -> bool:
        with self._run_lock:
            return self._running

    @property
    def last_result(self) -> SyncResult | None:
        return self._last_result

    @property
    def last_sync(self) -> datetime | None:
        return self._last_sync

    def _is_work_hours(self) -> bool:
        """Check if current time is within configured work hours."""
        from zoneinfo import ZoneInfo

        settings = get_settings()
        try:
            tz = ZoneInfo(settings.contact_sync_timezone)
        except Exception:
            tz = ZoneInfo("America/Los_Angeles")

        now = datetime.now(tz)
        return settings.contact_sync_work_hours_start <= now.hour < settings.contact_sync_work_hours_end

    def _get_stored_file_hash(self) -> str | None:
        """Get the last known file hash from the database."""
        db = get_db()
        row = db.execute(
            "SELECT file_hash FROM contact_sync_state WHERE id = 1"
        ).fetchone()
        return row[0] if row else None

    def _update_state(self, file_hash_val: str, result: SyncResult) -> None:
        """Update the singleton state row in the database."""
        db = get_db()
        db.execute(
            """INSERT INTO contact_sync_state (id, file_hash, last_sync_at, last_status,
               created_count, updated_count, deleted_count)
               VALUES (1, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
               file_hash = excluded.file_hash,
               last_sync_at = excluded.last_sync_at,
               last_status = excluded.last_status,
               created_count = excluded.created_count,
               updated_count = excluded.updated_count,
               deleted_count = excluded.deleted_count""",
            (
                file_hash_val,
                result.started_at.isoformat(),
                result.status,
                result.created,
                result.updated,
                result.deleted,
            ),
        )
        db.commit()

    def _log_sync_run(self, sync_id: str, result: SyncResult) -> None:
        """Append a row to the audit log table."""
        db = get_db()
        db.execute(
            """INSERT INTO contact_sync_log
               (sync_id, started_at, completed_at, status, created, updated, deleted,
                unchanged, errors_json, dry_run, file_hash, csv_row_count, duration_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                sync_id,
                result.started_at.isoformat(),
                result.completed_at.isoformat() if result.completed_at else None,
                result.status,
                result.created,
                result.updated,
                result.deleted,
                result.unchanged,
                json.dumps(result.errors),
                1 if result.dry_run else 0,
                result.file_hash,
                result.csv_row_count,
                result.duration_ms,
            ),
        )
        db.commit()

    def _diff_contacts(
        self, csv_contacts: list[ContactRecord]
    ) -> tuple[list[ContactRecord], list[ContactRecord], list[str]]:
        """
        Compare CSV contacts against stored per-row hashes.

        Returns:
            (to_create_or_update, unchanged, emails_to_delete)
        """
        db = get_db()
        rows = db.execute(
            "SELECT email_primary, row_hash, exchange_identity FROM contact_sync_contacts"
        ).fetchall()

        stored: dict[str, tuple[str, str]] = {}
        for email, rh, eid in rows:
            stored[email] = (rh, eid)

        csv_emails = {c.email_primary for c in csv_contacts}
        stored_emails = set(stored.keys())

        to_upsert: list[ContactRecord] = []
        unchanged: list[ContactRecord] = []

        for contact in csv_contacts:
            if contact.email_primary in stored:
                old_hash, _ = stored[contact.email_primary]
                if contact.row_hash() != old_hash:
                    to_upsert.append(contact)
                else:
                    unchanged.append(contact)
            else:
                to_upsert.append(contact)

        to_delete = list(stored_emails - csv_emails)

        return to_upsert, unchanged, to_delete

    def _apply_changes(
        self,
        to_upsert: list[ContactRecord],
        to_delete: list[str],
        result: SyncResult,
        managed_prefix: str,
    ) -> None:
        """
        Apply changes to the tracking database and invoke Exchange sync.

        For now, updates the tracking DB. Exchange push is in Phase 2.
        """
        db = get_db()
        settings = get_settings()

        # Safety check: abort if >20% of contacts would be deleted
        total_stored = db.execute(
            "SELECT COUNT(*) FROM contact_sync_contacts"
        ).fetchone()[0]

        if total_stored > 0 and len(to_delete) > 0:
            delete_pct = len(to_delete) / total_stored
            if delete_pct > 0.20:
                msg = (
                    f"Deletion threshold exceeded: {len(to_delete)}/{total_stored} "
                    f"({delete_pct:.0%}) contacts would be deleted. Aborting."
                )
                logger.error(msg)
                result.errors.append(msg)
                result.status = "failed"
                return

        dry_run = settings.contact_sync_dry_run

        # Process upserts
        for contact in to_upsert:
            existing = db.execute(
                "SELECT exchange_identity FROM contact_sync_contacts WHERE email_primary = ?",
                (contact.email_primary,),
            ).fetchone()

            if dry_run:
                if existing:
                    result.updated += 1
                else:
                    result.created += 1
                continue

            # Try Exchange sync (Phase 2 will add actual PowerShell call)
            exchange_identity = f"{managed_prefix}{contact.email_primary}"
            try:
                self._sync_to_exchange(contact, exchange_identity, is_update=bool(existing))
            except Exception as e:
                result.errors.append(f"{contact.email_primary}: {e}")
                continue

            if existing:
                result.updated += 1
            else:
                result.created += 1

            # Update tracking DB
            db.execute(
                """INSERT INTO contact_sync_contacts (email_primary, row_hash, exchange_identity)
                   VALUES (?, ?, ?)
                   ON CONFLICT(email_primary) DO UPDATE SET
                   row_hash = excluded.row_hash,
                   exchange_identity = excluded.exchange_identity,
                   updated_at = datetime('now')""",
                (contact.email_primary, contact.row_hash(), exchange_identity),
            )

        # Process deletions
        for email in to_delete:
            if dry_run:
                result.deleted += 1
                continue

            stored_row = db.execute(
                "SELECT exchange_identity FROM contact_sync_contacts WHERE email_primary = ?",
                (email,),
            ).fetchone()

            if stored_row:
                try:
                    self._delete_from_exchange(stored_row[0])
                except Exception as e:
                    result.errors.append(f"delete {email}: {e}")
                    continue

            result.deleted += 1
            db.execute(
                "DELETE FROM contact_sync_contacts WHERE email_primary = ?",
                (email,),
            )

        db.commit()

        if dry_run:
            result.status = "dry_run"
        else:
            result.status = "completed"

    def _sync_to_exchange(
        self, contact: ContactRecord, exchange_identity: str, is_update: bool
    ) -> None:
        """
        Push a contact to Exchange Online.

        Stub for Phase 1 - Phase 2 adds PowerShell subprocess.
        """
        logger.debug(
            "%s contact %s (%s)",
            "Updating" if is_update else "Creating",
            contact.email_primary,
            exchange_identity,
        )

    def _delete_from_exchange(self, exchange_identity: str) -> None:
        """
        Delete a contact from Exchange Online.

        Stub for Phase 1 - Phase 2 adds PowerShell subprocess.
        """
        logger.debug("Deleting contact %s", exchange_identity)

    def run_sync(self, force: bool = False) -> SyncResult:
        """
        Execute a full sync cycle.

        Args:
            force: Skip work-hours check and file-hash check

        Returns:
            SyncResult with counts and status
        """
        with self._run_lock:
            if self._running:
                return SyncResult(
                    started_at=datetime.now(UTC),
                    status="failed",
                    errors=["Sync already running"],
                )
            self._running = True

        result = SyncResult(started_at=datetime.now(UTC))
        sync_id = str(uuid.uuid4())

        try:
            settings = get_settings()

            if not settings.contact_sync_enabled and not force:
                result.status = "skipped"
                result.errors.append("Contact sync is disabled")
                return result

            csv_path = Path(settings.contact_sync_csv_path)
            if not csv_path.is_file():
                result.status = "failed"
                result.errors.append(f"CSV file not found: {csv_path}")
                return result

            # Work hours guard
            if not force and not self._is_work_hours():
                result.status = "skipped"
                result.errors.append("Outside work hours")
                return result

            # File hash change detection
            current_hash = file_hash(csv_path)
            result.file_hash = current_hash

            if not force:
                stored_hash = self._get_stored_file_hash()
                if stored_hash == current_hash:
                    result.status = "skipped"
                    result.errors.append("File unchanged")
                    return result

            # Read CSV
            contacts = read_contacts_csv(csv_path)
            result.csv_row_count = len(contacts)
            result.dry_run = settings.contact_sync_dry_run

            # Diff against stored state
            to_upsert, unchanged, to_delete = self._diff_contacts(contacts)
            result.unchanged = len(unchanged)

            logger.info(
                "Contact diff: %d upsert, %d unchanged, %d delete",
                len(to_upsert), len(unchanged), len(to_delete),
            )

            # Apply changes
            self._apply_changes(
                to_upsert,
                to_delete,
                result,
                settings.contact_sync_managed_prefix,
            )

            # Update state
            result.completed_at = datetime.now(UTC)
            result.duration_ms = int(
                (result.completed_at - result.started_at).total_seconds() * 1000
            )
            self._update_state(current_hash, result)
            self._last_result = result
            self._last_sync = result.started_at

            logger.info(
                "Contact sync %s: created=%d updated=%d deleted=%d unchanged=%d errors=%d",
                result.status,
                result.created,
                result.updated,
                result.deleted,
                result.unchanged,
                len(result.errors),
            )

        except Exception as e:
            logger.exception("Contact sync failed")
            result.status = "failed"
            result.completed_at = datetime.now(UTC)
            result.duration_ms = int(
                (result.completed_at - result.started_at).total_seconds() * 1000
            )
            result.errors.append(str(e))
            self._last_result = result

        finally:
            try:
                self._log_sync_run(sync_id, result)
            except Exception:
                logger.exception("Failed to log sync run %s", sync_id)
            with self._run_lock:
                self._running = False

        return result
