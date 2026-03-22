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

import ftfy


def _read_hub_contacts() -> list[ContactRecord]:
    """Read contacts from the hub DB table, with ftfy cleanup."""
    db = get_db()
    rows = db.execute(
        """SELECT email_primary, full_name, first_name, last_name, company,
                  job_title, phone_business, phone_mobile, street_address,
                  city, state, postal_code, country, category
           FROM contacts WHERE email_primary IS NOT NULL AND email_primary != ''"""
    ).fetchall()
    contacts: list[ContactRecord] = []
    for r in rows:
        contacts.append(ContactRecord(
            email_primary=r[0].lower(),
            full_name=ftfy.fix_text(r[1] or ""),
            first_name=ftfy.fix_text(r[2] or ""),
            last_name=ftfy.fix_text(r[3] or ""),
            company=ftfy.fix_text(r[4] or ""),
            job_title=ftfy.fix_text(r[5] or ""),
            phone_business=r[6] or "",
            phone_mobile=r[7] or "",
            street_address=ftfy.fix_text(r[8] or ""),
            city=ftfy.fix_text(r[9] or ""),
            state=ftfy.fix_text(r[10] or ""),
            postal_code=r[11] or "",
            country=ftfy.fix_text(r[12] or ""),
            category_canonical=r[13] or "",
        ))
    logger.info("Read %d contacts from hub", len(contacts))
    return contacts

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
        self._stop_requested = False
        self._run_lock = threading.Lock()
        self._initialized = True

    @property
    def is_running(self) -> bool:
        with self._run_lock:
            return self._running

    def stop(self) -> bool:
        """Request the running sync to stop after the current batch."""
        if self._running:
            self._stop_requested = True
            logger.info("Sync stop requested")
            return True
        return False

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
                json.dumps(result.errors + [f"[warn] {w}" for w in result.warnings]),
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
        Apply changes to the tracking database and push to Exchange.

        Updates tracking DB per-contact, then batches the Exchange push
        via PowerShell subprocess at the end.
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

        # Collect batches for Exchange push
        exchange_creates: list[ContactRecord] = []
        exchange_updates: list[ContactRecord] = []
        exchange_delete_ids: list[str] = []

        # Classify upserts into creates vs updates
        for contact in to_upsert:
            existing = db.execute(
                "SELECT exchange_identity FROM contact_sync_contacts WHERE email_primary = ?",
                (contact.email_primary,),
            ).fetchone()

            if existing:
                result.updated += 1
                if not dry_run:
                    exchange_updates.append(contact)
            else:
                result.created += 1
                if not dry_run:
                    exchange_creates.append(contact)

        # Classify deletions
        for email in to_delete:
            result.deleted += 1
            if not dry_run:
                stored_row = db.execute(
                    "SELECT exchange_identity FROM contact_sync_contacts WHERE email_primary = ?",
                    (email,),
                ).fetchone()
                if stored_row:
                    exchange_delete_ids.append(stored_row[0])

        if dry_run:
            from .exchange_sync import validate_contacts
            result.warnings = validate_contacts(to_upsert)
            result.status = "dry_run"
            return

        # Push to Exchange first, then update tracking DB based on what succeeded
        if exchange_creates or exchange_updates or exchange_delete_ids:
            ex_result = self._push_to_exchange(
                exchange_creates, exchange_updates, exchange_delete_ids, managed_prefix,
            )
            if ex_result.get("errors"):
                result.errors.extend(ex_result["errors"])
            ex_created = ex_result.get("created", 0)
            ex_updated = ex_result.get("updated", 0)
            ex_deleted = ex_result.get("deleted", 0)
            logger.info(
                "Exchange push: %d created, %d updated, %d deleted",
                ex_created, ex_updated, ex_deleted,
            )

            # Only track contacts that Exchange actually accepted
            for contact in exchange_creates[:ex_created]:
                identity = f"{managed_prefix}{contact.email_primary}"
                db.execute(
                    """INSERT INTO contact_sync_contacts (email_primary, row_hash, exchange_identity)
                       VALUES (?, ?, ?)
                       ON CONFLICT(email_primary) DO UPDATE SET
                       row_hash = excluded.row_hash,
                       exchange_identity = excluded.exchange_identity,
                       updated_at = datetime('now')""",
                    (contact.email_primary, contact.row_hash(), identity),
                )
            for contact in exchange_updates[:ex_updated]:
                identity = f"{managed_prefix}{contact.email_primary}"
                db.execute(
                    """INSERT INTO contact_sync_contacts (email_primary, row_hash, exchange_identity)
                       VALUES (?, ?, ?)
                       ON CONFLICT(email_primary) DO UPDATE SET
                       row_hash = excluded.row_hash,
                       exchange_identity = excluded.exchange_identity,
                       updated_at = datetime('now')""",
                    (contact.email_primary, contact.row_hash(), identity),
                )
            for email in to_delete[:ex_deleted]:
                db.execute(
                    "DELETE FROM contact_sync_contacts WHERE email_primary = ?",
                    (email,),
                )
            db.commit()

            # Update result counts to reflect what actually happened
            result.created = ex_created
            result.updated = ex_updated
            result.deleted = ex_deleted

        result.status = "completed"

    def _push_to_exchange(
        self,
        to_create: list[ContactRecord],
        to_update: list[ContactRecord],
        to_delete: list[str],
        managed_prefix: str,
    ) -> dict:
        """
        Batch push contacts to Exchange Online via PowerShell.

        Calls sync_contacts_to_exchange() which writes JSON, invokes
        PowerShell, and parses results. Graceful on auth/connection failure.
        """
        from .exchange_sync import sync_contacts_to_exchange

        try:
            return sync_contacts_to_exchange(
                to_create, to_update, to_delete, managed_prefix,
            )
        except Exception as e:
            logger.warning("Exchange push failed (will retry next cycle): %s", e)
            return {
                "created": 0,
                "updated": 0,
                "deleted": 0,
                "errors": [f"Exchange push failed: {e}"],
            }

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

            # Work hours guard
            if not force and not self._is_work_hours():
                result.status = "skipped"
                result.errors.append("Outside work hours")
                return result

            # Read contacts — from CSV if configured, otherwise from hub DB
            csv_path_str = settings.contact_sync_csv_path
            if csv_path_str and Path(csv_path_str).is_file():
                csv_path = Path(csv_path_str)
                current_hash = file_hash(csv_path)
                result.file_hash = current_hash
                if not force:
                    stored_hash = self._get_stored_file_hash()
                    if stored_hash == current_hash:
                        result.status = "skipped"
                        result.errors.append("File unchanged")
                        return result
                contacts = read_contacts_csv(csv_path)
            else:
                contacts = _read_hub_contacts()
                current_hash = ""

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
                self._stop_requested = False

        return result
