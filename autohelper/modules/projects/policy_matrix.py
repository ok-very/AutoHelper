"""
Policy matrix store — parse xlsx, persist as JSON, query by city/task.

Follows the same atomic-write pattern as ProjectStore.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from importlib import resources
from pathlib import Path
from typing import Any

from autohelper.shared.logging import get_logger
from autohelper.shared.paths import data_dir

from .types import PolicyMatrixData, PolicyNote, PolicyTopic

logger = get_logger(__name__)

MATRIX_PATH = data_dir() / "policy_matrix.json"

# xlsx stage label → template stage number(s)
STAGE_MAP: dict[str, int] = {
    "public art checklist": 1,
    "preliminary art plan": 2,
    "detailed public art plan": 3,
    "artist selection process": 5,
    "artist contract": 7,
    "artwork management": 8,
    "installation": 10,
    "final documentation": 11,
}


def _slugify(text: str) -> str:
    """Convert a topic label to a stable ID slug."""
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _detect_stage(label: str) -> int:
    """Try to infer stage from a topic label. Default to 0 (unmapped)."""
    lower = label.lower()
    for keyword, stage in STAGE_MAP.items():
        if keyword in lower:
            return stage
    return 0


def parse_xlsx(path: str) -> PolicyMatrixData:
    """
    Parse the BFA policy matrix xlsx into structured data.

    Expected layout:
    - Row 0 or 1: header row with city names
    - Column 0: topic/deliverable labels (possibly with stage group headers)
    - Remaining columns: city-specific policy text
    """
    try:
        import openpyxl
    except ImportError:
        raise ImportError(
            "openpyxl is required for xlsx import. Install with: pip install openpyxl"
        )

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    if ws is None:
        raise ValueError("No active worksheet found")

    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        raise ValueError("Spreadsheet has fewer than 2 rows")

    # Find header row — first row with at least 3 non-empty cells
    header_idx = 0
    for i, row in enumerate(rows):
        non_empty = sum(1 for c in row if c is not None and str(c).strip())
        if non_empty >= 3:
            header_idx = i
            break

    header = rows[header_idx]

    # Extract city columns (skip column 0 which is the topic label)
    city_columns: list[tuple[int, str]] = []
    city_names: dict[str, str] = {}
    for col_idx in range(1, len(header)):
        val = header[col_idx]
        if val is not None and str(val).strip():
            display_name = str(val).strip()
            city_id = _slugify(display_name)
            city_columns.append((col_idx, city_id))
            city_names[city_id] = display_name

    # Parse data rows
    topics: list[PolicyTopic] = []
    entries: dict[str, dict[str, str]] = {city_id: {} for _, city_id in city_columns}
    current_stage = 0
    order = 0

    for row_idx in range(header_idx + 1, len(rows)):
        row = rows[row_idx]
        if not row or row[0] is None:
            continue

        label = str(row[0]).strip()
        if not label:
            continue

        # Check if this is a stage header (no data in city columns)
        has_data = any(
            row[col_idx] is not None and str(row[col_idx]).strip()
            for col_idx, _ in city_columns
            if col_idx < len(row)
        )

        if not has_data:
            # Could be a stage/section header
            detected = _detect_stage(label)
            if detected:
                current_stage = detected
            continue

        # This is a topic row
        topic_id = _slugify(label)
        # Prefix with stage abbreviation for uniqueness
        stage_for_id = current_stage or _detect_stage(label)
        if stage_for_id:
            topic_id = f"s{stage_for_id}-{topic_id}"

        topic = PolicyTopic(
            id=topic_id,
            label=label,
            stage=stage_for_id,
            maps_to=[],
            order=order,
        )
        topics.append(topic)
        order += 1

        # Extract cell values
        for col_idx, city_id in city_columns:
            if col_idx < len(row) and row[col_idx] is not None:
                text = str(row[col_idx]).strip()
                if text:
                    entries[city_id][topic_id] = text

    wb.close()

    # Remove empty city entries
    entries = {k: v for k, v in entries.items() if v}

    return PolicyMatrixData(version="1.0", topics=topics, entries=entries, city_names=city_names)


class PolicyMatrixStore:
    """Manages the policy matrix JSON with atomic writes."""

    def __init__(self, path: Path = MATRIX_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _seed_if_empty(self) -> None:
        """Copy bundled seed data on first run (no policy_matrix.json yet)."""
        if self.path.exists():
            return
        try:
            seed = resources.files("autohelper.data").joinpath(
                "policy_matrix_seed.json"
            )
            with resources.as_file(seed) as seed_path:
                if seed_path.exists():
                    shutil.copy2(seed_path, self.path)
                    logger.info("Seeded policy matrix from bundled data")
        except Exception as e:
            logger.warning("Could not seed policy matrix: %s", e)

    def load(self) -> PolicyMatrixData:
        self._seed_if_empty()
        if not self.path.exists():
            return PolicyMatrixData()
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            pm = PolicyMatrixData.model_validate(data)
            # Backfill city_names from seed if runtime file predates the field
            if not pm.city_names:
                pm.city_names = self._load_seed_city_names()
            return pm
        except Exception as e:
            logger.error("Failed to load policy matrix: %s", e)
            return PolicyMatrixData()

    @staticmethod
    def _load_seed_city_names() -> dict[str, str]:
        """Load city_names from the bundled seed data."""
        try:
            seed = resources.files("autohelper.data").joinpath("policy_matrix_seed.json")
            with resources.as_file(seed) as path:
                data = json.loads(path.read_text(encoding="utf-8"))
                return data.get("city_names", {})
        except Exception:
            return {}

    def save(self, data: PolicyMatrixData) -> None:
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
            logger.error("Failed to save policy matrix: %s", e)
            raise

    def get_notes_for_city(self, city_id: str) -> dict[str, str]:
        """Return all topic_id → text entries for a city."""
        data = self.load()
        return dict(data.entries.get(city_id, {}))

    def get_notes_for_task(
        self, city_id: str, temp_id: str
    ) -> list[PolicyNote]:
        """Return all policy notes where maps_to includes the given temp_id."""
        data = self.load()
        city_entries = data.entries.get(city_id, {})
        if not city_entries:
            return []

        topic_map = {t.id: t for t in data.topics}
        notes: list[PolicyNote] = []
        for topic_id, text in city_entries.items():
            topic = topic_map.get(topic_id)
            if topic and temp_id in topic.maps_to:
                notes.append(PolicyNote(topic=topic.label, text=text))
        return notes

    def get_all_notes_for_city_tasks(
        self, city_id: str
    ) -> dict[str, list[PolicyNote]]:
        """Return temp_id → list of PolicyNote for all mapped tasks of a city."""
        data = self.load()
        city_entries = data.entries.get(city_id, {})
        if not city_entries:
            return {}

        result: dict[str, list[PolicyNote]] = {}
        for topic in data.topics:
            text = city_entries.get(topic.id)
            if not text:
                continue
            note = PolicyNote(topic=topic.label, text=text)
            for temp_id in topic.maps_to:
                result.setdefault(temp_id, []).append(note)
        return result


# Module-level singleton
_store: PolicyMatrixStore | None = None


def get_policy_matrix_store() -> PolicyMatrixStore:
    global _store
    if _store is None:
        _store = PolicyMatrixStore()
    return _store
