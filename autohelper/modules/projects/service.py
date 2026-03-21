"""
Projects service — business logic for project creation, resolution, and ClickUp provisioning.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from autohelper.config import get_settings
from autohelper.modules.clickup.client import ClickUp
from autohelper.modules.clickup.types import CreateTaskData
from autohelper.shared.ids import generate_project_id

from .policy_matrix import get_policy_matrix_store, parse_xlsx
from .store import get_project_store
from .template_resolver import (
    list_available_cities,
    load_city_overlay,
    resolve_template,
)
from .types import (
    CitySummary,
    CityOverlay,
    IntakeAnswers,
    PolicyMatrixData,
    PolicyTopic,
    ProjectRecord,
    ProjectStatus,
    ResolvedManifest,
)

logger = logging.getLogger(__name__)

TEMPLATE_TAG = "template_type:bfa_project"


def _get_token() -> str:
    settings = get_settings()
    token = settings.clickup_token  # type: ignore[attr-defined]
    if not token:
        raise ValueError("clickup_token not configured")
    return token


def _get_folder_or_space_id() -> tuple[str | None, str | None]:
    """Return (folder_id, space_id). At least one must be set."""
    settings = get_settings()
    folder_id = settings.clickup_folder_id or None  # type: ignore[attr-defined]
    space_id = settings.clickup_space_id or None  # type: ignore[attr-defined]
    if not folder_id and not space_id:
        raise ValueError("clickup_folder_id or clickup_space_id must be configured")
    return folder_id, space_id


# ── Read operations ──────────────────────────────────────────────


def list_cities() -> list[CitySummary]:
    """Return summary of all available cities (overlay files + policy matrix)."""
    overlays = list_available_cities()
    return [
        CitySummary(
            city_id=o.city_id,
            city_name=o.city_name,
            policy_version=o.policy_version,
            contribution_rate=o.budget_rules.contribution_rate,
            task_override_count=len(o.task_overrides),
            has_overlay=len(o.task_overrides) > 0 or o.policy_version != "current",
        )
        for o in overlays
    ]


def get_city(city_id: str) -> CityOverlay:
    """Return full city overlay config."""
    return load_city_overlay(city_id)


def preview_resolution(intake: IntakeAnswers) -> ResolvedManifest:
    """Dry-run template resolution — no persistence."""
    return resolve_template(intake)


def list_projects() -> list[ProjectRecord]:
    """Return all projects."""
    store = get_project_store()
    return store.list_all()


def get_project(project_id: str) -> ProjectRecord | None:
    """Return a single project by ID."""
    store = get_project_store()
    return store.get(project_id)


# ── Policy matrix ────────────────────────────────────────────────


def get_policy_matrix() -> PolicyMatrixData:
    """Return the full policy matrix."""
    return get_policy_matrix_store().load()


def save_policy_matrix(data: PolicyMatrixData) -> None:
    """Save the full policy matrix."""
    get_policy_matrix_store().save(data)


def update_policy_topics(topics: list[PolicyTopic]) -> None:
    """Update topics only (reorder, rename, map)."""
    store = get_policy_matrix_store()
    data = store.load()
    data.topics = topics
    store.save(data)


def update_policy_entry(city_id: str, topic_id: str, text: str) -> None:
    """Update a single cell in the policy matrix."""
    store = get_policy_matrix_store()
    data = store.load()
    if text.strip():
        data.entries.setdefault(city_id, {})[topic_id] = text
    else:
        # Empty text → remove the entry
        city = data.entries.get(city_id, {})
        city.pop(topic_id, None)
        if not city:
            data.entries.pop(city_id, None)
    store.save(data)


def import_policy_matrix(xlsx_path: str) -> PolicyMatrixData:
    """Import policy matrix from an xlsx file."""
    data = parse_xlsx(xlsx_path)
    store = get_policy_matrix_store()
    store.save(data)
    logger.info(
        "Imported policy matrix: %d topics, %d cities",
        len(data.topics),
        len(data.entries),
    )
    return data


# ── Email compose ────────────────────────────────────────────────


def list_project_templates(project_id: str) -> list[dict]:
    """Return email templates relevant to a project's resolved tasks, grouped by stage."""
    from .email_template_store import get_email_template_store

    store = get_project_store()
    project = store.get(project_id)
    if project is None:
        raise ValueError(f"Project {project_id} not found")

    manifest = resolve_template(project.intake)
    tmpl_store = get_email_template_store()

    # Collect template keys from resolved tasks
    stages: dict[int, list[dict]] = {}
    seen_keys: set[str] = set()

    for task in manifest.tasks:
        key = task.email_template_key
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)

        tmpl = tmpl_store.get(key)
        if tmpl is None:
            continue

        stage = task.stage
        if stage not in stages:
            stages[stage] = []
        stages[stage].append({
            "key": tmpl.key,
            "title": tmpl.title,
            "recipients": tmpl.recipients,
            "task_name": task.name,
            "task_temp_id": task.temp_id,
        })

    # Build stage-grouped result
    result = []
    for stage_info in manifest.stages:
        templates = stages.get(stage_info.number, [])
        if templates:
            result.append({
                "stage": stage_info.number,
                "name": stage_info.name,
                "templates": templates,
            })

    return result


def compose_email(project_id: str, template_key: str) -> dict:
    """Compose an email from a project's context and a template."""
    from .email_template_store import get_email_template_store

    store = get_project_store()
    project = store.get(project_id)
    if project is None:
        raise ValueError(f"Project {project_id} not found")

    overlay = load_city_overlay(project.intake.municipality)

    # Build merge context from intake + overlay
    intake = project.intake
    context: dict[str, str] = {
        "project_name": intake.project_name,
        "developer": intake.developer_name or "",
        "developer_name": intake.developer_name or "",
        "city_name": overlay.city_name,
        "municipality": overlay.city_name,
        "neighbourhood": intake.neighbourhood or "",
        "fsr": str(intake.fsr) if intake.fsr else "",
        "construction_cost": f"${intake.construction_cost:,.0f}" if intake.construction_cost else "",
    }

    # Config-level fields (PM name, etc.)
    from autohelper.config.store import ConfigStore
    cfg = ConfigStore().load()
    context["your_name"] = cfg.get("pm_name", "")
    context["project_coordinator"] = cfg.get("project_coordinator", "")

    tmpl_store = get_email_template_store()
    result = tmpl_store.merge(template_key, context)
    if result is None:
        raise ValueError(f"Template '{template_key}' not found")

    return result


# ── Write operations ─────────────────────────────────────────────


def create_project(intake: IntakeAnswers) -> ProjectRecord:
    """Create a draft project from intake answers."""
    manifest = resolve_template(intake)
    overlay = load_city_overlay(intake.municipality)

    project = ProjectRecord(
        id=generate_project_id(),
        project_name=intake.project_name,
        developer_name=intake.developer_name,
        municipality=intake.municipality,
        city_name=overlay.city_name,
        project_type=intake.project_type,
        intake=intake,
        budget=manifest.budget,
        resolved_task_count=manifest.total_tasks,
        status=ProjectStatus.DRAFT,
    )

    store = get_project_store()
    store.save(project)
    logger.info("Created project %s: %s (%s)", project.id, project.project_name, project.municipality)
    return project


async def provision_project(project_id: str) -> ProjectRecord:
    """
    Provision a project to ClickUp:
    1. Re-resolve template from saved intake
    2. Mark project as PROVISIONING (prevents double-trigger)
    3. Create ClickUp list in the configured folder
    4. Create Stage dropdown field, then all tasks (parents first, then children)
    5. Wire dependencies
    6. Update project record with ClickUp IDs → PROVISIONED
    """
    store = get_project_store()
    project = store.get(project_id)
    if project is None:
        raise ValueError(f"Project {project_id} not found")
    if project.status == ProjectStatus.PROVISIONING:
        raise ValueError(
            f"Project {project_id} has a provisioning attempt in progress or incomplete. "
            "Check ClickUp for partial data before retrying."
        )
    if project.status != ProjectStatus.DRAFT:
        raise ValueError(f"Project {project_id} is already {project.status.value}")

    # Re-resolve template
    manifest = resolve_template(project.intake)

    token = _get_token()
    folder_id, space_id = _get_folder_or_space_id()
    settings = get_settings()
    workspace_id = settings.clickup_workspace_id  # type: ignore[attr-defined]

    # Mark as PROVISIONING before any ClickUp calls
    project.status = ProjectStatus.PROVISIONING
    project.updated_at = datetime.now().isoformat()
    store.save(project)

    try:
        async with ClickUp(token) as cu:
            # Create folder if none specified — derive name from project
            # For phased projects (e.g., "Starlight - Lougheed P1"), strip phase suffix for folder
            if not folder_id and space_id:
                import re
                folder_name = re.sub(r'\s*P\d+$', '', project.project_name).strip()
                # Check if folder already exists (phased project reuse)
                existing_folders = await cu.spaces.get_folders(space_id)
                existing = next((f for f in existing_folders if f.name == folder_name), None)
                if existing:
                    folder_id = existing.id
                    logger.info("Reusing existing folder %s: %s", folder_id, folder_name)
                else:
                    new_folder = await cu.client.post(f"/space/{space_id}/folder", body={"name": folder_name})
                    folder_id = new_folder["id"]
                    logger.info("Created folder %s: %s", folder_id, folder_name)

            # Create list inside folder
            list_name = project.project_name
            if folder_id:
                cu_list = await cu.lists.create(folder_id, list_name)
            else:
                cu_list = await cu.lists.create_in_space(space_id, list_name)  # type: ignore[arg-type]
            list_id = cu_list.id
            logger.info("Created ClickUp list %s: %s", list_id, list_name)

            # Persist list ID immediately so we can find it if we crash
            project.clickup_list_id = list_id
            project.clickup_folder_id = folder_id
            project.clickup_workspace_id = workspace_id or None
            store.save(project)

            # Create "Stage" dropdown custom field on the new list
            stage_field_id: str | None = None
            stage_options: dict[str, str] = {}  # stage number → option ID
            try:
                field_result = await cu.client.post(f"/list/{list_id}/field", body={
                    "name": "Stage",
                    "type": "drop_down",
                    "type_config": {
                        "options": [
                            {"name": f"{s.number}. {s.name}"}
                            for s in manifest.stages
                        ],
                    },
                })
                field_data = field_result["field"]
                stage_field_id = field_data["id"]
                # Map stage numbers to the returned option IDs
                for opt in field_data["type_config"]["options"]:
                    # Option name format: "1. PROJECT INITIATION"
                    stage_num = opt["name"].split(".")[0].strip()
                    stage_options[stage_num] = opt["id"]
                logger.info("Created Stage field %s with %d options", stage_field_id, len(stage_options))

                # Persist field ID on project record
                project.clickup_stage_field_id = stage_field_id
                store.save(project)
            except Exception as e:
                logger.error("Failed to create Stage custom field: %s", e)

            # Create tasks — parents first, then children
            id_map: dict[str, str] = {}
            roots = [t for t in manifest.tasks if not t.parent_temp_id]
            children = [t for t in manifest.tasks if t.parent_temp_id]

            for task in roots + children:
                try:
                    parent_id: str | None = None
                    if task.parent_temp_id:
                        parent_id = id_map.get(task.parent_temp_id)

                    # Build description from policy notes
                    description: str | None = None
                    if task.policy_notes:
                        desc_parts = ["**Policy Guidance:**"]
                        for note in task.policy_notes:
                            desc_parts.append(f"\n**{note.topic}:** {note.text}")
                        description = "\n".join(desc_parts)

                    create_data = CreateTaskData(
                        name=task.name,
                        parent=parent_id,
                        tags=[TEMPLATE_TAG],
                        description=description,
                    )
                    created = await cu.tasks.create(list_id, create_data)
                    id_map[task.temp_id] = created.id

                    # Set Stage custom field
                    if stage_field_id:
                        option_id = stage_options.get(str(task.stage))
                        if option_id:
                            try:
                                await cu.custom_fields.set(created.id, stage_field_id, option_id)
                            except Exception as e:
                                logger.warning("Failed to set stage on %s: %s", task.temp_id, e)

                    # Throttle to stay under ClickUp rate limits
                    await asyncio.sleep(0.15)
                except Exception as e:
                    logger.error("Failed to create task %s: %s", task.temp_id, e)

            # Wire dependencies
            dep_count = 0
            for task in manifest.tasks:
                if not task.depends_on:
                    continue
                task_id = id_map.get(task.temp_id)
                if not task_id:
                    continue
                for dep_temp_id in task.depends_on:
                    dep_id = id_map.get(dep_temp_id)
                    if not dep_id:
                        continue
                    try:
                        await cu.client.post(
                            f"/task/{task_id}/dependency",
                            body={"depends_on": dep_id},
                        )
                        dep_count += 1
                        await asyncio.sleep(0.15)
                    except Exception as e:
                        logger.warning("Failed dep %s → %s: %s", task.temp_id, dep_temp_id, e)

            logger.info("Wired %d dependencies", dep_count)

    except Exception:
        # Project stays in PROVISIONING with partial ClickUp data
        logger.exception("Provisioning failed for project %s", project_id)
        raise

    # Success — update project record
    now = datetime.now().isoformat()
    project.status = ProjectStatus.PROVISIONED
    project.provisioned_at = now
    project.updated_at = now
    project.resolved_task_count = manifest.total_tasks
    project.budget = manifest.budget

    store.save(project)
    logger.info("Provisioned project %s → ClickUp list %s", project_id, list_id)
    return project


def delete_project(project_id: str) -> bool:
    """Delete a draft project. Cannot delete provisioned projects."""
    store = get_project_store()
    project = store.get(project_id)
    if project is None:
        return False
    if project.status != ProjectStatus.DRAFT:
        raise ValueError(f"Cannot delete {project.status.value} project")
    return store.delete(project_id)
