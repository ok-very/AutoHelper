"""
ClickUp service — manifest execution and template sync orchestration.
"""

from __future__ import annotations

import logging

from autohelper.config import get_settings

from .client import ClickUp, ClickUpApiError
from .manifest import (
    ImportManifest,
    ManifestExecutionResult,
    ManifestTask,
    TaskResult,
)
from .types import CreateTaskData

logger = logging.getLogger(__name__)


def _get_token() -> str:
    """Get ClickUp token from settings."""
    settings = get_settings()
    token = settings.clickup_token  # type: ignore[attr-defined]
    if not token:
        raise ValueError("clickup_token not configured")
    return token


def _topo_sort(tasks: list[ManifestTask]) -> list[ManifestTask]:
    """Sort tasks so parents come before children."""
    roots: list[ManifestTask] = []
    children: dict[str, list[ManifestTask]] = {}

    for t in tasks:
        if t.parent_temp_id:
            children.setdefault(t.parent_temp_id, []).append(t)
        else:
            roots.append(t)

    result: list[ManifestTask] = []

    def visit(task: ManifestTask) -> None:
        result.append(task)
        for child in children.get(task.temp_id, []):
            visit(child)

    for root in roots:
        visit(root)

    return result


async def execute_manifest(manifest: ImportManifest) -> ManifestExecutionResult:
    """
    Execute an import manifest — create tasks in ClickUp.

    Tasks are topologically sorted so parents are created before children.
    Parent temp_ids are resolved to real ClickUp IDs for subtask creation.
    Custom fields are set after task creation.
    """
    token = _get_token()
    sorted_tasks = _topo_sort(manifest.tasks)

    result = ManifestExecutionResult(
        session_id=manifest.session_id,
        total=len(sorted_tasks),
    )

    async with ClickUp(token) as cu:
        for task in sorted_tasks:
            try:
                # Resolve parent
                parent_id: str | None = None
                if task.parent_temp_id:
                    parent_id = result.id_map.get(task.parent_temp_id)
                    if not parent_id:
                        raise ValueError(
                            f"Parent temp_id '{task.parent_temp_id}' not found "
                            f"(not yet created or missing from manifest)"
                        )

                # Build create data
                create_data = CreateTaskData(
                    name=task.name,
                    description=task.description,
                    parent=parent_id,
                    tags=task.tags or None,
                    status=task.status,
                    custom_fields=[
                        {"id": cf.field_id, "value": cf.value}
                        for cf in task.custom_fields
                    ]
                    or None,
                )

                created = await cu.tasks.create(
                    manifest.target.list_id, create_data
                )

                result.id_map[task.temp_id] = created.id
                result.created += 1
                result.task_results.append(
                    TaskResult(
                        temp_id=task.temp_id,
                        clickup_id=created.id,
                        success=True,
                    )
                )

                logger.debug(
                    "Created task %s → %s (%s)",
                    task.temp_id,
                    created.id,
                    task.name,
                )

            except Exception as e:
                error_msg = f"Failed to create task '{task.name}' ({task.temp_id}): {e}"
                logger.error(error_msg)
                result.failed += 1
                result.errors.append(error_msg)
                result.task_results.append(
                    TaskResult(
                        temp_id=task.temp_id,
                        success=False,
                        error=str(e),
                    )
                )

    return result


async def validate_connection() -> dict[str, str]:
    """Validate ClickUp token by fetching workspace info."""
    token = _get_token()
    async with ClickUp(token) as cu:
        teams = await cu.teams.list()
        if not teams:
            raise ClickUpApiError("No workspaces found", 404)
        team = teams[0]
        return {"workspace_id": team.id, "workspace_name": team.name}
