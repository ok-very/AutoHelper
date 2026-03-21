"""
Project stage monitor — polls ClickUp to determine current stage of provisioned projects.

Given a project with a ClickUp list, fetches all tasks, reads the Stage custom field,
checks completion status, and derives: which stage is active, which tasks are done/pending,
and which email templates are ready to send.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .types import ProjectRecord, ProjectStatus

logger = logging.getLogger(__name__)


@dataclass
class TaskStatus:
    """Status of a single resolved task in ClickUp."""

    temp_id: str
    name: str
    stage: int
    clickup_status: str  # "open", "in progress", "complete", etc.
    is_complete: bool
    email_template_key: str | None = None


@dataclass
class StageStatus:
    """Status of a single project stage."""

    number: int
    name: str
    total_tasks: int = 0
    completed_tasks: int = 0
    in_progress_tasks: int = 0

    @property
    def is_complete(self) -> bool:
        return self.total_tasks > 0 and self.completed_tasks == self.total_tasks

    @property
    def is_active(self) -> bool:
        """Active = has at least one incomplete task and isn't fully complete."""
        return self.total_tasks > 0 and not self.is_complete

    @property
    def progress(self) -> float:
        return self.completed_tasks / self.total_tasks if self.total_tasks > 0 else 0


@dataclass
class ProjectStageReport:
    """Full stage report for a provisioned project."""

    project_id: str
    project_name: str
    clickup_list_id: str
    stages: list[StageStatus] = field(default_factory=list)
    tasks: list[TaskStatus] = field(default_factory=list)
    current_stage: int = 0  # The earliest incomplete stage
    total_tasks: int = 0
    completed_tasks: int = 0
    error: str | None = None

    @property
    def overall_progress(self) -> float:
        return self.completed_tasks / self.total_tasks if self.total_tasks > 0 else 0

    def templates_ready(self) -> list[TaskStatus]:
        """Return tasks in the current stage that have email templates and are not yet complete."""
        return [
            t for t in self.tasks
            if t.stage == self.current_stage
            and t.email_template_key
            and not t.is_complete
        ]

    def templates_sent(self) -> list[TaskStatus]:
        """Return completed tasks that had email templates."""
        return [
            t for t in self.tasks
            if t.email_template_key and t.is_complete
        ]


# Statuses ClickUp considers "done"
_DONE_STATUSES = {"complete", "closed", "done", "resolved"}


async def get_project_stage_report(project: ProjectRecord) -> ProjectStageReport:
    """Fetch ClickUp tasks for a provisioned project and derive stage status.

    Returns a ProjectStageReport with per-stage completion, current active stage,
    and template readiness.
    """
    from autohelper.config import get_settings
    from autohelper.modules.clickup.client import ClickUp

    report = ProjectStageReport(
        project_id=project.id,
        project_name=project.project_name,
        clickup_list_id=project.clickup_list_id or "",
    )

    if not project.clickup_list_id:
        report.error = "Project not provisioned to ClickUp"
        return report

    if project.status == ProjectStatus.DRAFT:
        report.error = "Project is still in draft"
        return report

    settings = get_settings()
    token = getattr(settings, "clickup_token", "")
    if not token:
        report.error = "ClickUp token not configured"
        return report

    try:
        # Re-resolve template to get the canonical task list with temp_ids
        from .template_resolver import resolve_template

        manifest = resolve_template(project.intake)
        template_tasks = {t.name.strip().lower(): t for t in manifest.tasks}

        # Fetch live ClickUp tasks
        async with ClickUp(token) as cu:
            clickup_tasks = await cu.tasks.list_all(
                project.clickup_list_id, include_closed=True
            )

        # Match ClickUp tasks to template tasks by name
        task_statuses: list[TaskStatus] = []
        for cu_task in clickup_tasks:
            cu_name = cu_task.name.strip().lower()
            tmpl = template_tasks.get(cu_name)

            status_str = cu_task.status.status.lower() if cu_task.status else "open"
            is_complete = status_str in _DONE_STATUSES or cu_task.date_closed is not None

            task_statuses.append(TaskStatus(
                temp_id=tmpl.temp_id if tmpl else "",
                name=cu_task.name,
                stage=tmpl.stage if tmpl else 0,
                clickup_status=status_str,
                is_complete=is_complete,
                email_template_key=tmpl.email_template_key if tmpl else None,
            ))

        report.tasks = task_statuses
        report.total_tasks = len(task_statuses)
        report.completed_tasks = sum(1 for t in task_statuses if t.is_complete)

        # Build per-stage status
        stage_map: dict[int, StageStatus] = {}
        for stage_info in manifest.stages:
            stage_map[stage_info.number] = StageStatus(
                number=stage_info.number,
                name=stage_info.name,
            )

        for t in task_statuses:
            s = stage_map.get(t.stage)
            if s is None:
                continue
            s.total_tasks += 1
            if t.is_complete:
                s.completed_tasks += 1
            elif t.clickup_status in ("in progress", "review"):
                s.in_progress_tasks += 1

        report.stages = sorted(stage_map.values(), key=lambda s: s.number)

        # Derive current stage: earliest stage that isn't fully complete
        report.current_stage = 0
        for s in report.stages:
            if s.is_active:
                report.current_stage = s.number
                break
        # If all stages are complete, current_stage = last stage
        if report.current_stage == 0 and report.stages:
            report.current_stage = report.stages[-1].number

    except Exception as e:
        report.error = str(e)
        logger.error("Stage report failed for %s: %s", project.id, e)

    return report
