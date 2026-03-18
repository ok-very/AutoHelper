"""
Sync artist records to a ClickUp list.

Each artist becomes a task with custom fields for key metadata.
Match by display_name (case-insensitive). Create or update, never delete.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from autohelper.config import get_settings
from autohelper.db import get_db

from .client import ClickUp
from .service import _get_token
from .types import CreateTaskData, UpdateTaskData

logger = logging.getLogger(__name__)


def _get_artist_list_id(override: str | None = None) -> str:
    if override:
        return override
    settings = get_settings()
    list_id = getattr(settings, "clickup_artist_list_id", "")
    if not list_id:
        raise ValueError("clickup_artist_list_id not configured")
    return list_id


def _build_description(m: dict[str, Any]) -> str:
    """Build a markdown task description from artist manifest."""
    parts: list[str] = []

    cats = m.get("categories", [])
    if cats:
        parts.append(f"**Categories:** {', '.join(cats)}")

    identity = m.get("identity", {})
    stage = identity.get("career_stage")
    if stage:
        parts.append(f"**Career Stage:** {stage}")

    tags = identity.get("identity_tags", {})
    identities = tags.get("identities", [])
    if identities:
        parts.append(f"**Identities:** {', '.join(identities)}")

    contact = m.get("contact", {})
    contact_parts = []
    if contact.get("email"):
        contact_parts.append(f"Email: {contact['email']}")
    if contact.get("website"):
        contact_parts.append(f"Web: {contact['website']}")
    if contact.get("phone"):
        contact_parts.append(f"Phone: {contact['phone']}")
    if contact_parts:
        parts.append(f"**Contact:** {' | '.join(contact_parts)}")

    return "\n".join(parts)


def _build_custom_fields(
    m: dict[str, Any],
    field_map: dict[str, str],
) -> list[dict[str, Any]]:
    """
    Build custom_fields payload from manifest data.
    field_map: { lowercase_field_name: field_id }
    """
    fields: list[dict[str, Any]] = []

    cats = m.get("categories", [])
    if "category" in field_map and cats:
        fields.append({"id": field_map["category"], "value": cats[0]})

    identity = m.get("identity", {})
    stage = identity.get("career_stage")
    if "career stage" in field_map and stage:
        fields.append({"id": field_map["career stage"], "value": stage})

    completeness = m.get("completeness", {})
    score = completeness.get("score")
    if "completeness" in field_map and score is not None:
        fields.append({"id": field_map["completeness"], "value": round(score * 100)})

    contact = m.get("contact", {})
    if "email" in field_map and contact.get("email"):
        fields.append({"id": field_map["email"], "value": contact["email"]})
    if "website" in field_map and contact.get("website"):
        fields.append({"id": field_map["website"], "value": contact["website"]})

    return fields


async def sync_artists(
    list_id: str,
    dry_run: bool = True,
    artist_ids: list[str] | None = None,
) -> dict[str, Any]:
    """
    Sync artist records to a ClickUp list.

    Returns { "created": int, "updated": int, "unchanged": int, "errors": [...] }
    """
    token = _get_token()
    db = get_db()

    # Load artists from DB
    if artist_ids:
        placeholders = ",".join("?" * len(artist_ids))
        rows = db.execute(
            f"SELECT artist_id, display_name, manifest_json FROM artists WHERE artist_id IN ({placeholders})",
            artist_ids,
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT artist_id, display_name, manifest_json FROM artists WHERE manifest_json IS NOT NULL"
        ).fetchall()

    artists: list[tuple[str, str, dict]] = []
    for artist_id, display_name, manifest_json in rows:
        if not manifest_json:
            continue
        try:
            m = json.loads(manifest_json)
        except (json.JSONDecodeError, TypeError):
            continue
        artists.append((artist_id, display_name, m))

    if not artists:
        return {"created": 0, "updated": 0, "unchanged": 0, "errors": []}

    async with ClickUp(token) as cu:
        # Get existing tasks in the target list
        existing_tasks = await cu.tasks.list_all(list_id, include_closed=True)

        # Build name → task map (case-insensitive)
        task_by_name: dict[str, Any] = {}
        for t in existing_tasks:
            task_by_name[t.name.strip().lower()] = t

        # Get custom field definitions
        list_fields = await cu.lists.get_fields(list_id)
        field_map: dict[str, str] = {}
        for f in list_fields:
            field_map[f.name.strip().lower()] = f.id

        created = 0
        updated = 0
        unchanged = 0
        errors: list[str] = []

        for artist_id, display_name, m in artists:
            try:
                description = _build_description(m)
                custom_fields = _build_custom_fields(m, field_map)
                identity_tags = m.get("identity", {}).get("identity_tags", {}).get("identities", [])

                existing = task_by_name.get(display_name.strip().lower())

                if existing:
                    # Check if update needed
                    needs_update = existing.description != description
                    if not needs_update:
                        unchanged += 1
                        continue

                    if dry_run:
                        updated += 1
                        continue

                    await cu.tasks.update(
                        existing.id,
                        UpdateTaskData(description=description),
                    )
                    # Update custom fields
                    for cf in custom_fields:
                        await cu.custom_fields.set(existing.id, cf["id"], cf["value"])
                    updated += 1
                else:
                    if dry_run:
                        created += 1
                        continue

                    task = await cu.tasks.create(
                        list_id,
                        CreateTaskData(
                            name=display_name,
                            description=description,
                            tags=[t.lower().replace(" ", "-") for t in identity_tags[:10]],
                            custom_fields=custom_fields,
                        ),
                    )
                    created += 1

            except Exception as e:
                errors.append(f"{display_name}: {e}")

    return {
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "errors": errors,
    }
