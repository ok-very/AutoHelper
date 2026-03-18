"""
Project store — JSON file persistence with atomic writes.

Follows the ConfigStore pattern: tempfile + fsync + os.replace.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from autohelper.shared.logging import get_logger
from autohelper.shared.paths import data_dir

from .types import ProjectRecord

logger = get_logger(__name__)

PROJECTS_PATH = data_dir() / "projects.json"


class ProjectStore:
    """Manages persistent project records."""

    def __init__(self, path: Path = PROJECTS_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load_raw(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"projects": {}}
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to load projects: %s", e)
            return {"projects": {}}

    def _save_raw(self, data: dict[str, Any]) -> None:
        dirpath = self.path.parent
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=str(dirpath), delete=False
            ) as tf:
                json.dump(data, tf, indent=2)
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
            logger.error("Failed to save projects: %s", e)
            raise

    def list_all(self) -> list[ProjectRecord]:
        data = self._load_raw()
        projects: list[ProjectRecord] = []
        for raw in data.get("projects", {}).values():
            try:
                projects.append(ProjectRecord.model_validate(raw))
            except Exception as e:
                logger.warning("Skipping invalid project record: %s", e)
        return projects

    def get(self, project_id: str) -> ProjectRecord | None:
        data = self._load_raw()
        raw = data.get("projects", {}).get(project_id)
        if raw is None:
            return None
        return ProjectRecord.model_validate(raw)

    def save(self, project: ProjectRecord) -> None:
        data = self._load_raw()
        data["projects"][project.id] = project.model_dump()
        self._save_raw(data)

    def delete(self, project_id: str) -> bool:
        data = self._load_raw()
        if project_id not in data.get("projects", {}):
            return False
        del data["projects"][project_id]
        self._save_raw(data)
        return True


# Module-level singleton
_store: ProjectStore | None = None


def get_project_store() -> ProjectStore:
    global _store
    if _store is None:
        _store = ProjectStore()
    return _store
