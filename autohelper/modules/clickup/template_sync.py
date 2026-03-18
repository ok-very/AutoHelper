"""
BFA template sync — keep ClickUp list in sync with ground truth template.

Loads bfa_templates.json, fetches current tasks from ClickUp, diffs,
and creates/updates tasks to match the template.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from importlib import resources
from typing import Any

from autohelper.config import get_settings

from .client import ClickUp
from .types import ClickUpTask, CreateTaskData

logger = logging.getLogger(__name__)

TEMPLATE_TAG = "template_type:bfa_project"


@dataclass
class SyncAction:
    """A single sync action."""

    action: str  # "create" | "update" | "orphan"
    temp_id: str
    name: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class SyncReport:
    """Result of a template sync run."""

    total_template: int = 0
    total_clickup: int = 0
    creates: list[SyncAction] = field(default_factory=list)
    updates: list[SyncAction] = field(default_factory=list)
    orphans: list[SyncAction] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    applied: bool = False


def load_template() -> dict[str, Any]:
    """Load the BFA template from the data directory."""
    data_pkg = resources.files("autohelper") / "data" / "bfa_templates.json"
    return json.loads(data_pkg.read_text(encoding="utf-8"))


def _match_task(
    template_name: str,
    clickup_tasks: dict[str, ClickUpTask],
) -> ClickUpTask | None:
    """Match a template task to a ClickUp task by name (case-insensitive, trimmed)."""
    normalized = template_name.strip().lower()
    return clickup_tasks.get(normalized)


async def sync_template(
    *,
    force: bool = False,
    list_id: str | None = None,
) -> SyncReport:
    """
    Sync BFA template tasks to ClickUp.

    Args:
        force: If True, apply changes. If False, dry-run only.
        list_id: Override list ID (defaults to settings.clickup_list_id).

    Returns:
        SyncReport with actions taken or planned.
    """
    settings = get_settings()
    token = settings.clickup_token  # type: ignore[attr-defined]
    if not token:
        raise ValueError("clickup_token not configured")

    target_list_id = list_id or settings.clickup_list_id  # type: ignore[attr-defined]
    if not target_list_id:
        raise ValueError("clickup_list_id not configured")

    template = load_template()
    template_tasks = template["tasks"]
    phase_field_id = template["phase_field_id"]
    phase_options = template["phase_options"]

    report = SyncReport(total_template=len(template_tasks))

    async with ClickUp(token) as cu:
        # Fetch all current tasks from ClickUp list
        existing = await cu.tasks.list_all(target_list_id, include_closed=True)
        report.total_clickup = len(existing)

        # Build name → task lookup (case-insensitive)
        clickup_by_name: dict[str, ClickUpTask] = {}
        for task in existing:
            key = task.name.strip().lower()
            clickup_by_name[key] = task

        # Track matched ClickUp task IDs
        matched_ids: set[str] = set()

        # Phase 1: Diff template against ClickUp
        for tmpl in template_tasks:
            match = _match_task(tmpl["name"], clickup_by_name)

            if match is None:
                # Task missing from ClickUp — needs creation
                report.creates.append(
                    SyncAction(
                        action="create",
                        temp_id=tmpl["temp_id"],
                        name=tmpl["name"],
                        details={
                            "stage": tmpl.get("stage"),
                            "is_milestone": tmpl.get("is_milestone", False),
                            "parent_temp_id": tmpl.get("parent_temp_id"),
                        },
                    )
                )
            else:
                matched_ids.add(match.id)

                # Check if phase custom field needs updating
                diffs: dict[str, Any] = {}
                stage = tmpl.get("stage")
                if stage and phase_field_id:
                    expected_option = phase_options.get(str(stage))
                    if expected_option:
                        current_value = None
                        for cf in match.custom_fields:
                            if cf.id == phase_field_id:
                                current_value = cf.value
                                break
                        if current_value != expected_option:
                            diffs["phase"] = {
                                "current": current_value,
                                "expected": expected_option,
                            }

                if diffs:
                    report.updates.append(
                        SyncAction(
                            action="update",
                            temp_id=tmpl["temp_id"],
                            name=tmpl["name"],
                            details=diffs,
                        )
                    )

        # Phase 2: Find orphans (ClickUp tasks not in template)
        for task in existing:
            if task.id not in matched_ids:
                # Check if this task has the BFA template tag
                has_tag = any(t.name == TEMPLATE_TAG for t in task.tags)
                if has_tag:
                    report.orphans.append(
                        SyncAction(
                            action="orphan",
                            temp_id="",
                            name=task.name,
                            details={"clickup_id": task.id},
                        )
                    )

        # Phase 3: Apply if force=True
        if force and (report.creates or report.updates):
            report.applied = True

            # Track temp_id → clickup_id for parent resolution
            id_map: dict[str, str] = {}

            # Map existing matched tasks
            for tmpl in template_tasks:
                match = _match_task(tmpl["name"], clickup_by_name)
                if match:
                    id_map[tmpl["temp_id"]] = match.id

            # Create missing tasks (roots first, then children)
            roots = [a for a in report.creates if not a.details.get("parent_temp_id")]
            children = [a for a in report.creates if a.details.get("parent_temp_id")]

            for action in roots + children:
                try:
                    parent_id: str | None = None
                    parent_temp_id = action.details.get("parent_temp_id")
                    if parent_temp_id:
                        parent_id = id_map.get(parent_temp_id)

                    # Find the template task for custom fields
                    tmpl_task = next(
                        t for t in template_tasks if t["temp_id"] == action.temp_id
                    )
                    stage = tmpl_task.get("stage")
                    custom_fields = None
                    if stage and phase_field_id:
                        option_id = phase_options.get(str(stage))
                        if option_id:
                            custom_fields = [
                                {"id": phase_field_id, "value": option_id}
                            ]

                    create_data = CreateTaskData(
                        name=action.name,
                        parent=parent_id,
                        tags=[TEMPLATE_TAG],
                        custom_fields=custom_fields,
                    )

                    created = await cu.tasks.create(target_list_id, create_data)
                    id_map[action.temp_id] = created.id
                    logger.info("Created template task: %s → %s", action.name, created.id)

                except Exception as e:
                    error = f"Failed to create '{action.name}': {e}"
                    logger.error(error)
                    report.errors.append(error)

            # Wire dependencies from template depends_on arrays
            dep_count = 0
            for tmpl in template_tasks:
                deps = tmpl.get("depends_on", [])
                if not deps:
                    continue
                task_id = id_map.get(tmpl["temp_id"])
                if not task_id:
                    continue
                for dep_temp_id in deps:
                    dep_id = id_map.get(dep_temp_id)
                    if not dep_id:
                        continue
                    try:
                        await cu.client.post(
                            f"/task/{task_id}/dependency",
                            body={"depends_on": dep_id},
                        )
                        dep_count += 1
                    except Exception as e:
                        error = f"Failed to add dependency {tmpl['temp_id']} → {dep_temp_id}: {e}"
                        logger.warning(error)
                        # Don't treat dep failures as hard errors
            logger.info("Wired %d dependencies", dep_count)

            # Apply updates (custom field changes)
            for action in report.updates:
                try:
                    tmpl_task = next(
                        t for t in template_tasks if t["temp_id"] == action.temp_id
                    )
                    match = _match_task(tmpl_task["name"], clickup_by_name)
                    if not match:
                        continue

                    if "phase" in action.details:
                        expected = action.details["phase"]["expected"]
                        await cu.custom_fields.set(
                            match.id, phase_field_id, expected
                        )
                        logger.info(
                            "Updated phase for '%s' → %s", action.name, expected
                        )

                except Exception as e:
                    error = f"Failed to update '{action.name}': {e}"
                    logger.error(error)
                    report.errors.append(error)

    logger.info(
        "Template sync %s: %d creates, %d updates, %d orphans, %d errors",
        "applied" if report.applied else "dry-run",
        len(report.creates),
        len(report.updates),
        len(report.orphans),
        len(report.errors),
    )

    return report
