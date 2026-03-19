"""
CSV import pipeline for seeding the contact hub.

Reads the master contacts CSV (9,068 records) and optional resolved_contacts.csv
(manual reconciliations), deduplicates by email, and inserts into the contacts hub table.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from autohelper.db import get_db
from autohelper.shared.ids import generate_id

logger = logging.getLogger(__name__)

# Map CSV columns to hub contact fields
COLUMN_MAP: dict[str, str] = {
    "first_name": "first_name",
    "last_name": "last_name",
    "full_name": "full_name",
    "company": "company",
    "job_title": "job_title",
    "email_primary": "email_primary",
    "email_secondary": "email_secondary",
    "phone_business": "phone_business",
    "phone_mobile": "phone_mobile",
    "category_canonical": "category",
    "notes": "notes",
    "confidence": "confidence",
    "staleness_label": "staleness_label",
    "last_seen": "last_seen",
    # Also support resolved_contacts.csv column names
    "category": "category",
    "email": "email_primary",
    "name": "full_name",
}


@dataclass
class ImportResult:
    """Result of a CSV import run."""

    total_csv_rows: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


def import_contacts_csv(
    csv_path: str | Path,
    overrides_path: str | Path | None = None,
    dry_run: bool = False,
) -> ImportResult:
    """
    Import contacts from the master CSV into the hub.

    Args:
        csv_path: Path to the master contacts CSV.
        overrides_path: Optional path to resolved_contacts.csv (manual reconciliations).
        dry_run: If True, parse and count but don't write.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    result = ImportResult()

    # Parse master CSV
    contacts = _parse_csv(csv_path)
    result.total_csv_rows = len(contacts)
    logger.info("Parsed %d contacts from %s", len(contacts), csv_path)

    # Apply overrides if provided
    if overrides_path:
        overrides_path = Path(overrides_path)
        if overrides_path.exists():
            overrides = _parse_csv(overrides_path)
            for email, data in overrides.items():
                if email in contacts:
                    contacts[email].update(data)
                else:
                    contacts[email] = data
            logger.info("Applied %d overrides from %s", len(overrides), overrides_path)

    if dry_run:
        result.created = len(contacts)
        return result

    # Insert into hub
    db = get_db()
    now = datetime.now().isoformat()

    for email, data in contacts.items():
        try:
            # Check if contact already exists
            existing = db.execute(
                "SELECT id FROM contacts WHERE LOWER(email_primary) = LOWER(?)",
                (email,),
            ).fetchone()

            full_name = data.get("full_name", "")
            if not full_name:
                full_name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()

            if existing:
                # Update existing record
                db.execute(
                    """UPDATE contacts SET
                        first_name = ?, last_name = ?, full_name = ?,
                        company = ?, job_title = ?,
                        email_secondary = ?, phone_business = ?, phone_mobile = ?,
                        category = ?, notes = ?,
                        confidence = ?, staleness_label = ?, last_seen = ?,
                        source = CASE WHEN source = 'manual' THEN source ELSE 'import' END,
                        updated_at = ?
                       WHERE id = ?""",
                    (
                        data.get("first_name", ""),
                        data.get("last_name", ""),
                        full_name,
                        data.get("company", ""),
                        data.get("job_title", ""),
                        data.get("email_secondary"),
                        data.get("phone_business"),
                        data.get("phone_mobile"),
                        data.get("category", ""),
                        data.get("notes"),
                        data.get("confidence", "MEDIUM"),
                        data.get("staleness_label", "Active"),
                        data.get("last_seen"),
                        now,
                        existing[0],
                    ),
                )
                result.updated += 1
            else:
                # Create new record
                contact_id = generate_id("con")
                db.execute(
                    """INSERT INTO contacts
                       (id, first_name, last_name, full_name, company, job_title,
                        email_primary, email_secondary, phone_business, phone_mobile,
                        category, notes, confidence, staleness_label, last_seen,
                        source, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'import', ?, ?)""",
                    (
                        contact_id,
                        data.get("first_name", ""),
                        data.get("last_name", ""),
                        full_name,
                        data.get("company", ""),
                        data.get("job_title", ""),
                        email.lower(),
                        data.get("email_secondary"),
                        data.get("phone_business"),
                        data.get("phone_mobile"),
                        data.get("category", ""),
                        data.get("notes"),
                        data.get("confidence", "MEDIUM"),
                        data.get("staleness_label", "Active"),
                        data.get("last_seen"),
                        now,
                        now,
                    ),
                )
                result.created += 1

        except Exception as e:
            result.errors.append(f"{email}: {e}")
            logger.warning("Import error for %s: %s", email, e)

    db.commit()
    logger.info(
        "Import complete: %d created, %d updated, %d errors",
        result.created, result.updated, len(result.errors),
    )
    return result


def _parse_csv(path: Path) -> dict[str, dict[str, str]]:
    """Parse a CSV file into a dict keyed by email_primary."""
    contacts: dict[str, dict[str, str]] = {}

    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header row: {path}")

        # Build column mapping
        col_map: dict[str, str] = {}
        for header in reader.fieldnames:
            normalized = header.strip().lower().replace(" ", "_").replace("-", "_")
            if normalized in COLUMN_MAP:
                col_map[header] = COLUMN_MAP[normalized]

        if "email_primary" not in col_map.values():
            raise ValueError(f"CSV missing email column. Headers: {reader.fieldnames}")

        for row in reader:
            data: dict[str, str] = {}
            for csv_col, field_name in col_map.items():
                value = (row.get(csv_col) or "").strip()
                if value:
                    data[field_name] = value

            email = data.get("email_primary", "").lower()
            if not email:
                continue

            data["email_primary"] = email
            contacts[email] = data

    return contacts
