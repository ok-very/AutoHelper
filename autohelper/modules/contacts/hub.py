"""
Contact Hub — central resolution layer for all contact operations.

Provides CRUD, search, project association management, and resolution
for template merge fields and mail triage sender matching.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from autohelper.db import get_db
from autohelper.shared.ids import generate_id

logger = logging.getLogger(__name__)

# Canonical contact slots — keys used in associations, values are display labels
CONTACT_SLOTS: dict[str, str] = {
    # Team
    "contact":              "Contact",
    "owner":                "Owner",
    "architect":            "Architect",
    "landscape":            "Landscape",
    # Stage contacts
    "ppap":                 "PPAP",
    "dpap":                 "DPAP",
    "eoi":                  "EOI",
    # Selection
    "sp1":                  "SP#1",
    "ao":                   "AO",
    "sp2":                  "SP#2",
    "selection_panel":      "Selection Panel",
    # Artists
    "shortlisted_artist":   "Shortlisted Artist",
    "selected_artist":      "Selected Artist",
    # Advisory
    "community_advisory":   "Community Advisory",
    "indigenous_advisor":   "Indigenous Advisor",
    # Generic
    "project_coordinator":  "Project Coordinator",
    "engineer":             "Engineer",
    "city_planner":         "City Planner",
    "other":                "Other",
}

# Backward compat — old role names that map to canonical slots
ROLE_ALIASES: dict[str, str] = {
    "developer":            "contact",
    "landscape_architect":  "landscape",
    "panel_member":         "selection_panel",
    "community_advisor":    "community_advisory",
    "artist":               "selected_artist",
}

VALID_ROLES = set(CONTACT_SLOTS.keys()) | set(ROLE_ALIASES.keys())

# Singular slots — only one contact expected per project
SINGULAR_SLOTS = {
    "contact", "owner", "architect", "landscape",
    "ppap", "dpap", "eoi", "ao",
    "selected_artist", "project_coordinator", "engineer", "city_planner",
}

# Slot → merge field names for email template resolution
SLOT_TO_MERGE: dict[str, list[str]] = {
    "contact":             ["developer_contact_name"],
    "city_planner":        ["city_contact_name", "city_planner_name"],
    "architect":           ["architect_name"],
    "landscape":           ["landscape_architect_name"],
    "selected_artist":     ["artist_name"],
    "project_coordinator": ["coordinator_name"],
    "engineer":            ["engineer_name"],
}


def normalize_role(role: str) -> str:
    """Normalize a role to its canonical slot name."""
    return ROLE_ALIASES.get(role, role)


@dataclass
class HubContact:
    """A contact record from the hub."""

    id: str
    first_name: str = ""
    last_name: str = ""
    full_name: str = ""
    company: str = ""
    job_title: str = ""
    email_primary: str = ""
    email_secondary: str | None = None
    phone_business: str | None = None
    phone_mobile: str | None = None
    category: str = ""
    notes: str | None = None
    confidence: str = "MEDIUM"
    staleness_label: str = "Active"
    last_seen: str | None = None
    exchange_id: str | None = None
    clickup_contact_ref: str | None = None
    source: str = "manual"
    street_address: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    country: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass
class ContactAssociation:
    """A link between a contact and a project."""

    id: str
    contact_id: str
    project_id: str
    role: str
    is_primary: bool = True
    notes: str | None = None
    created_at: str = ""
    # Joined fields (populated when querying with contact or project info)
    contact_name: str = ""
    contact_email: str = ""
    contact_company: str = ""
    project_name: str = ""


@dataclass
class ContactSearchResult:
    """Paginated search result."""

    contacts: list[HubContact]
    total: int
    offset: int
    limit: int


def _row_to_contact(row: tuple) -> HubContact:
    """Convert a database row to a HubContact."""
    return HubContact(
        id=row[0],
        first_name=row[1] or "",
        last_name=row[2] or "",
        full_name=row[3] or "",
        company=row[4] or "",
        job_title=row[5] or "",
        email_primary=row[6] or "",
        email_secondary=row[7],
        phone_business=row[8],
        phone_mobile=row[9],
        category=row[10] or "",
        notes=row[11],
        confidence=row[12] or "MEDIUM",
        staleness_label=row[13] or "Active",
        last_seen=row[14],
        exchange_id=row[15],
        clickup_contact_ref=row[16],
        source=row[17] or "manual",
        street_address=row[18] or "",
        city=row[19] or "",
        state=row[20] or "",
        postal_code=row[21] or "",
        country=row[22] or "",
        created_at=row[23] or "",
        updated_at=row[24] or "",
    )


CONTACT_COLUMNS = """id, first_name, last_name, full_name, company, job_title,
    email_primary, email_secondary, phone_business, phone_mobile,
    category, notes, confidence, staleness_label, last_seen,
    exchange_id, clickup_contact_ref, source,
    street_address, city, state, postal_code, country,
    created_at, updated_at"""


# ── CRUD ─────────────────────────────────────────────────────────


def get_contact(contact_id: str) -> HubContact | None:
    """Fetch a single contact by ID."""
    db = get_db()
    row = db.execute(
        f"SELECT {CONTACT_COLUMNS} FROM contacts WHERE id = ?",
        (contact_id,),
    ).fetchone()
    return _row_to_contact(row) if row else None


def get_contact_by_email(email: str) -> HubContact | None:
    """Fetch a single contact by email (case-insensitive)."""
    db = get_db()
    row = db.execute(
        f"SELECT {CONTACT_COLUMNS} FROM contacts WHERE LOWER(email_primary) = LOWER(?)",
        (email,),
    ).fetchone()
    return _row_to_contact(row) if row else None


def create_contact(
    *,
    first_name: str = "",
    last_name: str = "",
    full_name: str = "",
    company: str = "",
    job_title: str = "",
    email_primary: str,
    email_secondary: str | None = None,
    phone_business: str | None = None,
    phone_mobile: str | None = None,
    category: str = "",
    notes: str | None = None,
    confidence: str = "MEDIUM",
    staleness_label: str = "Active",
    last_seen: str | None = None,
    source: str = "manual",
    street_address: str = "",
    city: str = "",
    state: str = "",
    postal_code: str = "",
    country: str = "",
) -> HubContact:
    """Create a new contact in the hub."""
    if not email_primary:
        raise ValueError("email_primary is required")

    # Auto-derive full_name if not provided
    if not full_name:
        full_name = f"{first_name} {last_name}".strip()

    contact_id = generate_id("con")
    now = datetime.now().isoformat()
    db = get_db()
    db.execute(
        """INSERT INTO contacts
           (id, first_name, last_name, full_name, company, job_title,
            email_primary, email_secondary, phone_business, phone_mobile,
            category, notes, confidence, staleness_label, last_seen,
            source, street_address, city, state, postal_code, country,
            created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            contact_id, first_name, last_name, full_name, company, job_title,
            email_primary.lower(), email_secondary, phone_business, phone_mobile,
            category, notes, confidence, staleness_label, last_seen,
            source, street_address, city, state, postal_code, country,
            now, now,
        ),
    )
    db.commit()
    logger.info("Created contact %s: %s <%s>", contact_id, full_name, email_primary)
    return get_contact(contact_id)  # type: ignore[return-value]


def update_contact(contact_id: str, **fields: str | None) -> HubContact | None:
    """Update contact fields. Only provided fields are updated."""
    allowed = {
        "first_name", "last_name", "full_name", "company", "job_title",
        "email_primary", "email_secondary", "phone_business", "phone_mobile",
        "category", "notes", "confidence", "staleness_label", "last_seen",
        "exchange_id", "clickup_contact_ref", "source",
        "street_address", "city", "state", "postal_code", "country",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_contact(contact_id)

    updates["updated_at"] = datetime.now().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [contact_id]

    db = get_db()
    db.execute(f"UPDATE contacts SET {set_clause} WHERE id = ?", values)
    db.commit()
    return get_contact(contact_id)


def queue_for_exchange_sync(contact: HubContact) -> None:
    """Queue a hub contact for Exchange sync on the next cycle.

    Inserts/updates the contact_sync_contacts tracking row so the
    ContactSyncService picks it up. Does NOT invoke PowerShell directly.
    """
    if not contact.email_primary:
        return

    from autohelper.config import get_settings
    settings = get_settings()
    managed_prefix = getattr(settings, "contact_sync_managed_prefix", "BFA-")

    # Build a row_hash from the contact fields for change detection
    import hashlib
    parts = [
        contact.email_primary, contact.full_name or "",
        contact.first_name or "", contact.last_name or "",
        contact.company or "", contact.job_title or "",
    ]
    row_hash = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
    exchange_identity = f"{managed_prefix}{contact.email_primary}"

    db = get_db()
    db.execute(
        """INSERT INTO contact_sync_contacts (email_primary, row_hash, exchange_identity)
           VALUES (?, ?, ?)
           ON CONFLICT(email_primary) DO UPDATE SET
           row_hash = excluded.row_hash,
           exchange_identity = excluded.exchange_identity,
           updated_at = datetime('now')""",
        (contact.email_primary, row_hash, exchange_identity),
    )
    db.commit()
    logger.debug("Queued %s for Exchange sync", contact.email_primary)


def delete_contact(contact_id: str) -> bool:
    """Delete a contact and its associations."""
    db = get_db()
    cursor = db.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    db.commit()
    return cursor.rowcount > 0


# ── Search ───────────────────────────────────────────────────────


def search_contacts(
    *,
    query: str = "",
    category: str = "",
    staleness: str = "",
    limit: int = 50,
    offset: int = 0,
) -> ContactSearchResult:
    """Search contacts with optional filters."""
    conditions: list[str] = []
    params: list[str] = []

    if query:
        conditions.append(
            "(full_name LIKE ? OR email_primary LIKE ? OR company LIKE ?)"
        )
        q = f"%{query}%"
        params.extend([q, q, q])

    if category:
        conditions.append("category = ?")
        params.append(category)

    if staleness:
        conditions.append("staleness_label = ?")
        params.append(staleness)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    db = get_db()

    # Count total
    count_row = db.execute(
        f"SELECT COUNT(*) FROM contacts {where}", params
    ).fetchone()
    total = count_row[0] if count_row else 0

    # Fetch page
    rows = db.execute(
        f"""SELECT {CONTACT_COLUMNS} FROM contacts {where}
            ORDER BY full_name ASC
            LIMIT ? OFFSET ?""",
        params + [limit, offset],
    ).fetchall()

    return ContactSearchResult(
        contacts=[_row_to_contact(r) for r in rows],
        total=total,
        offset=offset,
        limit=limit,
    )


def list_categories() -> list[dict]:
    """Return distinct categories with counts."""
    db = get_db()
    rows = db.execute(
        "SELECT category, COUNT(*) as cnt FROM contacts GROUP BY category ORDER BY cnt DESC"
    ).fetchall()
    return [{"category": r[0], "count": r[1]} for r in rows]


def get_contact_count() -> int:
    """Return total number of contacts."""
    db = get_db()
    row = db.execute("SELECT COUNT(*) FROM contacts").fetchone()
    return row[0] if row else 0


# ── Associations ─────────────────────────────────────────────────


def associate_contact(
    *,
    contact_id: str,
    project_id: str,
    role: str,
    is_primary: bool = True,
    notes: str | None = None,
) -> ContactAssociation:
    """Link a contact to a project with a role (slot).

    Accepts both canonical slot names and legacy role aliases.
    """
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role: {role}. Must be one of: {', '.join(sorted(VALID_ROLES))}")
    role = normalize_role(role)

    assoc_id = generate_id("pca")
    now = datetime.now().isoformat()
    db = get_db()
    db.execute(
        """INSERT OR REPLACE INTO project_contact_associations
           (id, contact_id, project_id, role, is_primary, notes, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (assoc_id, contact_id, project_id, role, int(is_primary), notes, now),
    )
    db.commit()
    logger.info("Associated contact %s → project %s as %s", contact_id, project_id, role)
    return ContactAssociation(
        id=assoc_id, contact_id=contact_id, project_id=project_id,
        role=role, is_primary=is_primary, notes=notes, created_at=now,
    )


def remove_association(association_id: str) -> bool:
    """Remove a project-contact association."""
    db = get_db()
    cursor = db.execute(
        "DELETE FROM project_contact_associations WHERE id = ?",
        (association_id,),
    )
    db.commit()
    return cursor.rowcount > 0


def get_project_contacts(project_id: str) -> list[ContactAssociation]:
    """Get all contacts associated with a project, with contact details."""
    db = get_db()
    rows = db.execute(
        """SELECT pca.id, pca.contact_id, pca.project_id, pca.role,
                  pca.is_primary, pca.notes, pca.created_at,
                  c.full_name, c.email_primary, c.company
           FROM project_contact_associations pca
           JOIN contacts c ON c.id = pca.contact_id
           WHERE pca.project_id = ?
           ORDER BY pca.role, c.full_name""",
        (project_id,),
    ).fetchall()

    return [
        ContactAssociation(
            id=r[0], contact_id=r[1], project_id=r[2], role=r[3],
            is_primary=bool(r[4]), notes=r[5], created_at=r[6],
            contact_name=r[7] or "", contact_email=r[8] or "",
            contact_company=r[9] or "",
        )
        for r in rows
    ]


def get_contact_projects(contact_id: str) -> list[ContactAssociation]:
    """Get all projects associated with a contact."""
    db = get_db()
    rows = db.execute(
        """SELECT pca.id, pca.contact_id, pca.project_id, pca.role,
                  pca.is_primary, pca.notes, pca.created_at
           FROM project_contact_associations pca
           WHERE pca.contact_id = ?
           ORDER BY pca.created_at DESC""",
        (contact_id,),
    ).fetchall()

    return [
        ContactAssociation(
            id=r[0], contact_id=r[1], project_id=r[2], role=r[3],
            is_primary=bool(r[4]), notes=r[5], created_at=r[6],
        )
        for r in rows
    ]


# ── Resolution (for template merge + mail triage) ───────────────


def resolve_project_contact(project_id: str, role: str) -> HubContact | None:
    """Resolve the primary contact for a role on a project."""
    db = get_db()
    # Prefix columns with c. to avoid ambiguity with pca.id
    cols = ", ".join(f"c.{col.strip()}" for col in CONTACT_COLUMNS.split(","))
    row = db.execute(
        f"""SELECT {cols} FROM contacts c
            JOIN project_contact_associations pca ON pca.contact_id = c.id
            WHERE pca.project_id = ? AND pca.role = ? AND pca.is_primary = 1
            LIMIT 1""",
        (project_id, role),
    ).fetchone()
    return _row_to_contact(row) if row else None


def resolve_sender(email: str) -> dict | None:
    """
    Resolve an email sender to a hub contact with project associations.
    Used by mail triage to enrich incoming emails.
    """
    contact = get_contact_by_email(email)
    if not contact:
        return None

    associations = get_contact_projects(contact.id)

    return {
        "contact_id": contact.id,
        "full_name": contact.full_name,
        "company": contact.company,
        "category": contact.category,
        "projects": [
            {
                "project_id": a.project_id,
                "role": a.role,
                "is_primary": a.is_primary,
            }
            for a in associations
        ],
    }


def resolve_merge_fields(project_id: str) -> dict[str, str]:
    """
    Build a merge-field dict for a project from the contact hub.
    Used by compose_email() to fill {{name}}, {{developer_contact_name}}, etc.
    """
    fields: dict[str, str] = {}
    for slot, field_names in SLOT_TO_MERGE.items():
        contact = resolve_project_contact(project_id, slot)
        if contact:
            for fname in field_names:
                fields[fname] = contact.full_name
            fields[f"{slot}_email"] = contact.email_primary

    return fields
