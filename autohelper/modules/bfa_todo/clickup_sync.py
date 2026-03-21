"""
ClickUp → BFA To Do List sync.

Pulls provisioned projects from the Projects module, fetches live task status
from ClickUp via stage_monitor, and creates/updates BFA To Do entries.

Workflow:
  PMs work in ClickUp daily → Monday morning this runs →
  To Do list regenerated → deployed to Google Docs for owner.
"""

from __future__ import annotations

import logging
from typing import Any

from autohelper.shared.ids import generate_id

logger = logging.getLogger(__name__)


def sync_from_clickup() -> dict[str, Any]:
    """Pull all provisioned projects and sync into BFA To Do entries.

    For each provisioned project:
    - If no To Do entry exists, create one with fields from the project record
    - If entry exists, update phase from ClickUp task completion
    - Sections (next_steps, milestones) are PM-managed, not overwritten

    Returns sync summary.
    """
    from autohelper.modules.projects.service import list_projects
    from autohelper.modules.projects.types import ProjectStatus
    from .pipeline.repo import BfaProjectRepo

    repo = BfaProjectRepo()
    all_projects = list_projects()
    provisioned = [p for p in all_projects if p.status in (ProjectStatus.PROVISIONED, ProjectStatus.ACTIVE)]

    created = 0
    updated = 0
    errors: list[str] = []

    for project in provisioned:
        try:
            # Check if To Do entry already exists (match by project name)
            existing = _find_existing_entry(repo, project.project_name, project.developer_name)

            if existing:
                # Update phase if we can determine it
                _update_entry_phase(existing, project)
                repo.upsert(existing)
                updated += 1
            else:
                # Create new entry from project record
                entry = _project_to_todo_entry(project)
                repo.upsert(entry)
                created += 1

        except Exception as e:
            errors.append(f"{project.project_name}: {e}")
            logger.warning("Sync error for %s: %s", project.project_name, e)

    logger.info("ClickUp sync: %d created, %d updated, %d errors", created, updated, len(errors))
    return {
        "provisioned_count": len(provisioned),
        "created": created,
        "updated": updated,
        "errors": errors,
    }


async def sync_with_stage_report() -> dict[str, Any]:
    """Sync with live ClickUp task status via stage_monitor.

    Fetches actual task completion from ClickUp to determine current stage,
    derives next steps from the dependency graph, and updates To Do entries.
    """
    from autohelper.modules.projects.service import list_projects
    from autohelper.modules.projects.stage_monitor import get_project_stage_report
    from autohelper.modules.projects.template_resolver import resolve_template
    from autohelper.modules.projects.types import ProjectStatus
    from .pipeline.repo import BfaProjectRepo

    repo = BfaProjectRepo()
    all_projects = list_projects()
    provisioned = [p for p in all_projects if p.status in (ProjectStatus.PROVISIONED, ProjectStatus.ACTIVE)]

    updated = 0
    errors: list[str] = []

    for project in provisioned:
        if not project.clickup_list_id:
            continue
        try:
            report = await get_project_stage_report(project)
            manifest = resolve_template(project.intake)

            existing = _find_existing_entry(repo, project.project_name, project.developer_name)
            if not existing:
                existing = _project_to_todo_entry(project)

            sections = existing.get("sections", {})

            # Update phase from stage report
            if report.current_stage and report.stages:
                stage = next((s for s in report.stages if s.number == report.current_stage), None)
                if stage:
                    existing["bfa_phase_canonical"] = stage.name
                    existing["bfa_phase_display"] = stage.name
                    sections.setdefault("bfa_phase", {})
                    sections["bfa_phase"]["text"] = stage.name
                    sections["bfa_phase"]["html"] = f'<p><strong>Project Status:</strong> {stage.name}</p>'

            # Derive next steps from dependency graph
            completed_ids = {t.temp_id for t in report.tasks if t.is_complete}
            ready_tasks = []
            for task in manifest.tasks:
                if task.temp_id in completed_ids:
                    continue
                deps = task.depends_on or []
                unmet = [d for d in deps if d not in completed_ids]
                if not unmet:
                    ready_tasks.append(task)

            if ready_tasks:
                lines = [t.name for t in ready_tasks]
                sections.setdefault("next_steps", {})
                sections["next_steps"]["text"] = "\n".join(lines)
                sections["next_steps"]["html"] = "<ul>" + "".join(f"<li>{n}</li>" for n in lines) + "</ul>"

            # Progress summary in milestones
            if report.stages:
                progress_lines = []
                for s in report.stages:
                    if s.total_tasks > 0:
                        if s.is_complete:
                            progress_lines.append(f"Stage {s.number}: {s.name} — complete")
                        elif s.completed_tasks > 0:
                            progress_lines.append(f"Stage {s.number}: {s.name} — {s.completed_tasks}/{s.total_tasks}")
                if progress_lines:
                    sections.setdefault("milestones", {})
                    sections["milestones"]["text"] = "\n".join(progress_lines)
                    sections["milestones"]["html"] = "<br>".join(progress_lines)

            existing["sections"] = sections
            repo.upsert(existing)
            updated += 1

        except Exception as e:
            errors.append(f"{project.project_name}: {e}")
            logger.warning("Stage sync error for %s: %s", project.project_name, e)

    return {"updated": updated, "errors": errors}


def _find_existing_entry(
    repo: Any, project_name: str, developer_name: str | None
) -> dict[str, Any] | None:
    """Find an existing BFA To Do entry matching this project."""
    all_entries = repo.get_all()
    name_lower = project_name.lower()
    dev_lower = (developer_name or "").lower()

    for entry in all_entries:
        if entry.get("type") != "project":
            continue
        fields = entry.get("fields", {})
        entry_name = fields.get("project_name", "").lower()
        entry_client = fields.get("client", "").lower()

        # Match on project name or client + name combo
        if name_lower in entry_name or entry_name in name_lower:
            return entry
        if dev_lower and dev_lower in entry_client:
            return entry

    return None


def _project_to_todo_entry(project: Any) -> dict[str, Any]:
    """Convert a Projects module ProjectRecord to a BFA To Do entry dict."""
    # Parse developer shortname from project name (e.g., "Keltic - 6620 Sussex" → "Keltic")
    client = project.developer_name or ""
    parts = project.project_name.split(" - ")
    if len(parts) >= 2:
        client = parts[0].strip()

    return {
        "uid": generate_id("bfa"),
        "slug": project.project_name.lower().replace(" ", "-").replace(".", ""),
        "type": "project",
        "status": "active",
        "source": "clickup",
        "fields": {
            "client": client,
            "project_name": project.project_name,
            "city": project.city_name.replace("City of ", "").replace("District of ", ""),
            "artists_text": "",
            "contacts_text": "",
            "owner_team": "BFA",
        },
        "header": {
            "text": project.project_name,
            "html": f'<h3><span style="font-weight:700;text-decoration:underline;font-size:11pt">{project.project_name}</span></h3>',
        },
        "sections": {
            "bfa_phase": {"text": "Stage 1", "html": "<p><strong>Project Status:</strong> Stage 1</p>"},
            "next_steps": {"text": "", "html": ""},
            "content": {"text": "", "html": ""},
        },
        "bfa_phase_canonical": "Stage 1",
        "bfa_phase_display": "Stage 1",
    }
