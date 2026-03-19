"""
Email template store — persistent JSON storage with seed-from-markdown capability.

Follows the same atomic-write pattern as PolicyMatrixStore.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from autohelper.shared.logging import get_logger
from autohelper.shared.paths import data_dir

from .types import EmailTemplateDef, EmailTemplateData

logger = get_logger(__name__)

STORE_PATH = data_dir() / "email_templates.json"


class EmailTemplateStore:
    """Manages email templates JSON with atomic writes."""

    def __init__(self, path: Path = STORE_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _seed_if_empty(self) -> None:
        """Seed from markdown files on first run."""
        if self.path.exists():
            return
        try:
            data = seed_from_markdown()
            self.save(data)
            logger.info(
                "Seeded %d email templates from markdown files",
                len(data.templates),
            )
        except Exception as e:
            logger.warning("Could not seed email templates: %s", e)

    def load(self) -> EmailTemplateData:
        self._seed_if_empty()
        if not self.path.exists():
            return EmailTemplateData()
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            return EmailTemplateData.model_validate(data)
        except Exception as e:
            logger.error("Failed to load email templates: %s", e)
            return EmailTemplateData()

    def save(self, data: EmailTemplateData) -> None:
        dirpath = self.path.parent
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=str(dirpath), delete=False
            ) as tf:
                json.dump(data.model_dump(), tf, indent=2)
                tf.flush()
                os.fsync(tf.fileno())
                temp_path = Path(tf.name)
            os.replace(str(temp_path), str(self.path))
        except Exception as e:
            try:
                if "temp_path" in locals() and temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass
            logger.error("Failed to save email templates: %s", e)
            raise

    def get(self, key: str) -> EmailTemplateDef | None:
        """Get a template by key."""
        data = self.load()
        for t in data.templates:
            if t.key == key:
                return t
        # Try zero-padded match (1.1 → 01.1)
        parts = key.split(".")
        if len(parts) == 2:
            padded = f"{int(parts[0]):02d}.{parts[1]}"
            for t in data.templates:
                if t.key == padded:
                    return t
        return None

    def update_template(self, key: str, updates: dict[str, Any]) -> bool:
        """Update a single template by key. Returns True if found."""
        data = self.load()
        for i, t in enumerate(data.templates):
            if t.key == key:
                for field, value in updates.items():
                    if hasattr(t, field):
                        setattr(t, field, value)
                # Re-derive merge fields from subject + body
                combined = t.subject + " " + t.body_html
                t.merge_fields = sorted(set(re.findall(r"\{\{(\w+)\}\}", combined)))
                data.templates[i] = t
                self.save(data)
                return True
        return False


# Module-level singleton
_store: EmailTemplateStore | None = None


def get_email_template_store() -> EmailTemplateStore:
    global _store
    if _store is None:
        _store = EmailTemplateStore()
    return _store


# ── Seed from markdown ──────────────────────────────────────────────


def _infer_recipient_role(title: str, body: str) -> str:
    """Infer recipient role from template title and body content."""
    lower = (title + " " + body).lower()
    if "city" in lower or "tamara" in lower or "pac" in lower:
        return "city"
    if "artist" in lower and ("invite" in lower or "notify" in lower or "confirm" in lower):
        return "artist"
    if "selection panel" in lower or "sp member" in lower or "community advisory" in lower:
        return "panel"
    if "invoice" in lower or "internal" in lower:
        return "internal"
    return "developer"


def _build_task_key_map() -> dict[str, list[str]]:
    """Build email_template_key → [temp_id] mapping from bfa_templates.json."""
    import json as _json
    from importlib import resources

    data_pkg = resources.files("autohelper") / "data" / "bfa_templates.json"
    template = _json.loads(data_pkg.read_text(encoding="utf-8"))
    mapping: dict[str, list[str]] = {}
    for task in template["tasks"]:
        key = task.get("email_template_key")
        if key:
            mapping.setdefault(key, []).append(task["temp_id"])
    return mapping


def seed_from_markdown() -> EmailTemplateData:
    """Parse markdown files and build the template data store."""
    from autohelper.modules.clickup.email_templates import TemplateRegistry

    # Force fresh load (bypass singleton cache)
    TemplateRegistry.reset()
    registry = TemplateRegistry.load()

    task_map = _build_task_key_map()

    templates: list[EmailTemplateDef] = []
    for key in registry.all_keys():
        tmpl = registry.get(key)
        if tmpl is None:
            continue

        # Parse stage from key (01.x → stage 1, 02.x → stage 2, etc.)
        stage = _key_to_stage(key)

        templates.append(
            EmailTemplateDef(
                key=tmpl.key,
                title=tmpl.title,
                stage=stage,
                subject=tmpl.subject_template,
                body_html=tmpl.body_html,
                merge_fields=tmpl.merge_fields,
                maps_to=task_map.get(tmpl.key, []),
                order=len(templates),
                recipient_role=_infer_recipient_role(tmpl.title, tmpl.body_markdown),
            )
        )

    logger.info("Seeded %d email templates from markdown", len(templates))
    return EmailTemplateData(templates=templates)


# Template key prefix → BFA stage mapping
_KEY_STAGE_MAP: dict[int, int] = {
    1: 1,   # 01.x → Stage 1: Project Initiation
    2: 2,   # 02.x → Stage 2: PPAP
    3: 3,   # 03.x → Stage 3: DPAP
    4: 5,   # 04.x → Stage 5: Artist Selection (longlist)
    5: 6,   # 05.x → Stage 6: Artist Orientation
    6: 6,   # 06.x → Stage 6: Selection Panel #2
    7: 7,   # 07.x → Stage 7: Artist Contract
    8: 10,  # 08.x → Stage 10: Installation
    9: 11,  # 09.x → Stage 11: Close-Out
}


def _key_to_stage(key: str) -> int:
    """Map template key prefix to BFA stage number."""
    try:
        prefix = int(key.split(".")[0])
        return _KEY_STAGE_MAP.get(prefix, prefix)
    except (ValueError, IndexError):
        return 0
