"""
BFA Todo SQLite repository.

Replaces the YAML-based store.py with SQLite-backed storage.
Returns dicts shaped like the old YAML for backward compat with service.py.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from autohelper.db.conn import get_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Helpers: dict <-> row conversion
# ---------------------------------------------------------------------------

_TRANSIENT_SECTION_KEYS = {"runs", "inline_html"}


def _project_to_row(p: dict[str, Any]) -> dict[str, Any]:
    """Convert a project dict (as used by service.py) into column values."""
    fields = p.get("fields", {})
    header = p.get("header", {})
    return {
        "uid": p["uid"],
        "slug": p.get("slug", ""),
        "fingerprint": p.get("fingerprint"),
        "type": p.get("type", "project"),
        "status": p.get("status", "active"),
        "source": p.get("source"),
        "project_record_id": p.get("project_record_id"),
        "fields_json": json.dumps(fields, ensure_ascii=False),
        "header_text": header.get("text"),
        "header_html": header.get("html"),
        "phase_display": p.get("bfa_phase_display"),
        "phase_canonical": p.get("bfa_phase_canonical"),
        "next_steps_json": json.dumps(p.get("next_steps", []), ensure_ascii=False),
        "updated_at": _now(),
    }


def _sections_from_project(uid: str, p: dict[str, Any]) -> list[tuple]:
    """Extract (uid, name, text, html) tuples for bfa_sections."""
    rows = []
    now = _now()
    for name, sec in p.get("sections", {}).items():
        text = sec.get("text")
        html = sec.get("html")
        rows.append((uid, name, text, html, now, now))
    return rows


def _row_to_project(row: Any, sections: list[Any]) -> dict[str, Any]:
    """Reconstruct a project dict from a DB row + section rows."""
    fields = json.loads(row["fields_json"]) if row["fields_json"] else {}
    header = {}
    if row["header_text"] or row["header_html"]:
        header = {"text": row["header_text"] or "", "html": row["header_html"] or ""}

    secs = {}
    for s in sections:
        secs[s["name"]] = {"text": s["text"] or "", "html": s["html"] or ""}

    project = {
        "uid": row["uid"],
        "slug": row["slug"],
        "fingerprint": row["fingerprint"],
        "type": row["type"],
        "status": row["status"],
        "source": row["source"],
        "project_record_id": row["project_record_id"] if "project_record_id" in row.keys() else None,
        "fields": fields,
        "header": header,
        "sections": secs,
        "bfa_phase_display": row["phase_display"] or "TBC",
        "bfa_phase_canonical": row["phase_canonical"] or "TBC",
        "next_steps": json.loads(row["next_steps_json"]) if row["next_steps_json"] else [],
    }

    # Backward compat: contacts_text and artists_text at top level
    if "contacts_text" in fields:
        project["contacts_text"] = fields["contacts_text"]
    if "artists_text" in fields:
        project["artists_text"] = fields["artists_text"]

    return project


# ---------------------------------------------------------------------------
# BfaProjectRepo
# ---------------------------------------------------------------------------

class BfaProjectRepo:
    """SQLite repository for BFA projects, preambles, and sections."""

    def get(self, uid: str) -> dict[str, Any] | None:
        db = get_db()
        row = db.execute("SELECT * FROM bfa_projects WHERE uid = ?", (uid,)).fetchone()
        if not row:
            return None
        sections = db.execute(
            "SELECT * FROM bfa_sections WHERE project_uid = ?", (uid,)
        ).fetchall()
        return _row_to_project(row, sections)

    def get_all(self, include_archived: bool = False) -> list[dict[str, Any]]:
        db = get_db()
        if include_archived:
            rows = db.execute("SELECT * FROM bfa_projects ORDER BY slug").fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM bfa_projects WHERE status != 'archived' ORDER BY slug"
            ).fetchall()

        # Batch-load all sections
        uids = [r["uid"] for r in rows]
        if not uids:
            return []
        placeholders = ",".join("?" * len(uids))
        all_sections = db.execute(
            f"SELECT * FROM bfa_sections WHERE project_uid IN ({placeholders})",
            tuple(uids),
        ).fetchall()

        # Group sections by uid
        sec_by_uid: dict[str, list] = {}
        for s in all_sections:
            sec_by_uid.setdefault(s["project_uid"], []).append(s)

        return [_row_to_project(r, sec_by_uid.get(r["uid"], [])) for r in rows]

    def get_by_type(self, *types: str) -> list[dict[str, Any]]:
        db = get_db()
        placeholders = ",".join("?" * len(types))
        rows = db.execute(
            f"SELECT * FROM bfa_projects WHERE type IN ({placeholders}) ORDER BY slug",
            tuple(types),
        ).fetchall()
        uids = [r["uid"] for r in rows]
        if not uids:
            return []
        uid_ph = ",".join("?" * len(uids))
        all_sections = db.execute(
            f"SELECT * FROM bfa_sections WHERE project_uid IN ({uid_ph})",
            tuple(uids),
        ).fetchall()
        sec_by_uid: dict[str, list] = {}
        for s in all_sections:
            sec_by_uid.setdefault(s["project_uid"], []).append(s)
        return [_row_to_project(r, sec_by_uid.get(r["uid"], [])) for r in rows]

    def upsert(self, project: dict[str, Any]) -> None:
        db = get_db()
        row = _project_to_row(project)
        uid = row["uid"]

        db.execute("""
            INSERT INTO bfa_projects (uid, slug, fingerprint, type, status, source,
                project_record_id, fields_json, header_text, header_html,
                phase_display, phase_canonical, next_steps_json, updated_at)
            VALUES (:uid, :slug, :fingerprint, :type, :status, :source,
                :project_record_id, :fields_json, :header_text, :header_html,
                :phase_display, :phase_canonical, :next_steps_json, :updated_at)
            ON CONFLICT(uid) DO UPDATE SET
                slug=excluded.slug, fingerprint=excluded.fingerprint, type=excluded.type,
                status=excluded.status, source=excluded.source,
                project_record_id=COALESCE(excluded.project_record_id, bfa_projects.project_record_id),
                fields_json=excluded.fields_json,
                header_text=excluded.header_text, header_html=excluded.header_html,
                phase_display=excluded.phase_display, phase_canonical=excluded.phase_canonical,
                next_steps_json=excluded.next_steps_json, updated_at=excluded.updated_at
        """, row)

        # Replace sections
        db.execute("DELETE FROM bfa_sections WHERE project_uid = ?", (uid,))
        section_rows = _sections_from_project(uid, project)
        if section_rows:
            db.executemany(
                "INSERT INTO bfa_sections (project_uid, name, text, html, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                section_rows,
            )
        db.commit()

    def upsert_batch(self, projects: list[dict[str, Any]]) -> None:
        """Insert/update multiple projects in a single transaction."""
        db = get_db()
        try:
            for p in projects:
                row = _project_to_row(p)
                uid = row["uid"]
                db.execute("""
                    INSERT INTO bfa_projects (uid, slug, fingerprint, type, status, source,
                        project_record_id, fields_json, header_text, header_html,
                        phase_display, phase_canonical, next_steps_json, updated_at)
                    VALUES (:uid, :slug, :fingerprint, :type, :status, :source,
                        :project_record_id, :fields_json, :header_text, :header_html,
                        :phase_display, :phase_canonical, :next_steps_json, :updated_at)
                    ON CONFLICT(uid) DO UPDATE SET
                        slug=excluded.slug, fingerprint=excluded.fingerprint, type=excluded.type,
                        status=excluded.status, source=excluded.source,
                        project_record_id=COALESCE(excluded.project_record_id, bfa_projects.project_record_id),
                        fields_json=excluded.fields_json,
                        header_text=excluded.header_text, header_html=excluded.header_html,
                        phase_display=excluded.phase_display, phase_canonical=excluded.phase_canonical,
                        next_steps_json=excluded.next_steps_json, updated_at=excluded.updated_at
                """, row)
                db.execute("DELETE FROM bfa_sections WHERE project_uid = ?", (uid,))
                section_rows = _sections_from_project(uid, p)
                if section_rows:
                    db.executemany(
                        "INSERT INTO bfa_sections (project_uid, name, text, html, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        section_rows,
                    )
            db.commit()
        except Exception:
            db.rollback()
            raise

    def update_section(self, uid: str, name: str, text: str, html: str) -> None:
        db = get_db()
        now = _now()
        db.execute("""
            INSERT INTO bfa_sections (project_uid, name, text, html, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_uid, name) DO UPDATE SET
                text=excluded.text, html=excluded.html, updated_at=excluded.updated_at
        """, (uid, name, text, html, now, now))
        db.execute(
            "UPDATE bfa_projects SET updated_at = ? WHERE uid = ?", (now, uid)
        )
        db.commit()

    def archive(self, uid: str) -> bool:
        db = get_db()
        cursor = db.execute(
            "UPDATE bfa_projects SET status = 'archived', updated_at = ? WHERE uid = ?",
            (_now(), uid),
        )
        db.commit()
        return cursor.rowcount > 0

    def count(self, include_archived: bool = False) -> int:
        db = get_db()
        if include_archived:
            row = db.execute("SELECT COUNT(*) as c FROM bfa_projects").fetchone()
        else:
            row = db.execute(
                "SELECT COUNT(*) as c FROM bfa_projects WHERE status != 'archived'"
            ).fetchone()
        return row["c"] if row else 0


# ---------------------------------------------------------------------------
# BfaAliasRepo
# ---------------------------------------------------------------------------

class BfaAliasRepo:
    """SQLite repository for BFA alias/identity mappings."""

    def get(self) -> dict[str, Any]:
        db = get_db()
        row = db.execute("SELECT * FROM bfa_aliases WHERE id = 1").fetchone()
        if not row:
            return {
                "version": 1,
                "mappings": [],
                "rollups": [],
                "ignored": [],
                "client_aliases": {},
            }
        return {
            "version": row["version"],
            "mappings": json.loads(row["mappings_json"]) if row["mappings_json"] else [],
            "rollups": json.loads(row["rollups_json"]) if row["rollups_json"] else [],
            "ignored": json.loads(row["ignored_json"]) if row["ignored_json"] else [],
            "client_aliases": json.loads(row["client_aliases_json"]) if row["client_aliases_json"] else {},
        }

    def save(self, aliases: dict[str, Any]) -> None:
        db = get_db()
        db.execute("""
            INSERT INTO bfa_aliases (id, version, mappings_json, rollups_json, ignored_json, client_aliases_json, updated_at)
            VALUES (1, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                version=excluded.version, mappings_json=excluded.mappings_json,
                rollups_json=excluded.rollups_json, ignored_json=excluded.ignored_json,
                client_aliases_json=excluded.client_aliases_json, updated_at=excluded.updated_at
        """, (
            aliases.get("version", 1),
            json.dumps(aliases.get("mappings", []), ensure_ascii=False),
            json.dumps(aliases.get("rollups", []), ensure_ascii=False),
            json.dumps(aliases.get("ignored", []), ensure_ascii=False),
            json.dumps(aliases.get("client_aliases", {}), ensure_ascii=False),
            _now(),
        ))
        db.commit()


# ---------------------------------------------------------------------------
# YAML seed (one-time migration from YAML files to SQLite)
# ---------------------------------------------------------------------------

def seed_from_yaml() -> int:
    """Load existing YAML data into SQLite. Returns count of projects seeded."""
    from . import config
    from .store import load_all_projects, load_aliases

    projects = load_all_projects(include_archived=True)
    if not projects:
        return 0

    repo = BfaProjectRepo()
    repo.upsert_batch(projects)

    # Seed aliases
    aliases = load_aliases()
    if aliases.get("mappings"):
        alias_repo = BfaAliasRepo()
        alias_repo.save(aliases)

    return len(projects)
