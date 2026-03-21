"""
Template resolver — base template + city overlay + conditions → ResolvedManifest.

Pipeline:
  load_base_template() → load_city_overlay(city_id) → apply_overrides()
  → resolve_conditions(intake) → validate_deps() → calculate_budget()
  → ResolvedManifest
"""

from __future__ import annotations

import copy
import json
import logging
from importlib import resources
from typing import Any

from .types import (
    BudgetCalculation,
    BudgetRules,
    CityOverlay,
    IntakeAnswers,
    PolicyNote,
    ResolvedManifest,
    ResolvedTask,
    StageInfo,
    TaskSource,
)

logger = logging.getLogger(__name__)


def load_base_template() -> dict[str, Any]:
    """Load the BFA base template from package data."""
    data_pkg = resources.files("autohelper") / "data" / "bfa_templates.json"
    return json.loads(data_pkg.read_text(encoding="utf-8"))


def load_city_overlay(city_id: str) -> CityOverlay:
    """Load a city overlay JSON, falling back to a default overlay for cities
    that exist in the policy matrix but have no dedicated overlay file."""
    overlay_pkg = resources.files("autohelper") / "data" / "city_overlays" / f"{city_id}.json"
    try:
        data = json.loads(overlay_pkg.read_text(encoding="utf-8"))
        return CityOverlay.model_validate(data)
    except (FileNotFoundError, TypeError):
        # No overlay file — build a default overlay using policy matrix city_names
        from .policy_matrix import get_policy_matrix_store

        pm = get_policy_matrix_store().load()
        city_name = pm.city_names.get(city_id, city_id.replace("-", " ").title())
        return CityOverlay(city_id=city_id, city_name=city_name)


def list_available_cities() -> list[CityOverlay]:
    """List all available cities — overlay files merged with policy matrix cities.

    Cities with dedicated overlay JSON files get their full customization.
    Cities that exist in the policy matrix but have no overlay get a default overlay
    with base template settings and their policy notes still attached during resolution.
    """
    # 1. Load overlay files
    overlays_dir = resources.files("autohelper") / "data" / "city_overlays"
    by_id: dict[str, CityOverlay] = {}
    for item in overlays_dir.iterdir():
        name = getattr(item, "name", str(item))
        if name.endswith(".json"):
            try:
                data = json.loads(item.read_text(encoding="utf-8"))
                overlay = CityOverlay.model_validate(data)
                by_id[overlay.city_id] = overlay
            except Exception:
                logger.warning("Failed to load city overlay: %s", name)

    # 2. Merge in cities from the policy matrix that don't have overlays
    try:
        from .policy_matrix import get_policy_matrix_store

        pm = get_policy_matrix_store().load()
        for city_id in pm.entries:
            if city_id not in by_id:
                city_name = pm.city_names.get(city_id, city_id.replace("-", " ").title())
                by_id[city_id] = CityOverlay(city_id=city_id, city_name=city_name)
    except Exception:
        logger.debug("Could not load policy matrix for city list merge")

    return sorted(by_id.values(), key=lambda o: o.city_name)


def _tasks_to_resolved(raw_tasks: list[dict[str, Any]]) -> list[ResolvedTask]:
    """Convert raw JSON tasks to ResolvedTask models."""
    return [
        ResolvedTask(
            temp_id=t["temp_id"],
            name=t["name"],
            stage=t["stage"],
            is_milestone=t.get("is_milestone", False),
            parent_temp_id=t.get("parent_temp_id"),
            depends_on=t.get("depends_on", []),
            email_template_key=t.get("email_template_key"),
            condition=t.get("condition"),
            source=TaskSource.BASE,
        )
        for t in raw_tasks
    ]


def _apply_overrides(tasks: list[ResolvedTask], overlay: CityOverlay) -> list[ResolvedTask]:
    """Apply city overlay modifications and additions to the task list."""
    task_map = {t.temp_id: t for t in tasks}

    for override in overlay.task_overrides:
        if override.action == "modify" and override.temp_id:
            target = task_map.get(override.temp_id)
            if target and override.changes:
                for key, value in override.changes.items():
                    if hasattr(target, key):
                        setattr(target, key, value)
                target.source = TaskSource.OVERLAY
                logger.debug("Modified task %s: %s", override.temp_id, override.changes)

        elif override.action == "add" and override.task:
            t = override.task
            new_task = ResolvedTask(
                temp_id=t.temp_id,
                name=t.name,
                stage=t.stage,
                is_milestone=t.is_milestone,
                parent_temp_id=t.parent_temp_id,
                depends_on=t.depends_on,
                email_template_key=t.email_template_key,
                condition=t.condition,
                source=TaskSource.ADDED,
            )
            task_map[new_task.temp_id] = new_task
            logger.debug("Added overlay task: %s", new_task.temp_id)

    # Remove tasks listed in task_removals
    for temp_id in overlay.task_removals:
        if temp_id in task_map:
            del task_map[temp_id]
            logger.debug("Removed task: %s", temp_id)

    return list(task_map.values())


def _resolve_conditions(
    tasks: list[ResolvedTask],
    intake: IntakeAnswers,
    overlay: CityOverlay,
) -> tuple[list[ResolvedTask], dict[str, bool]]:
    """Filter tasks based on conditions, returning kept tasks and applied conditions."""
    # Build effective conditions: overlay defaults + intake overrides
    effective: dict[str, bool] = dict(overlay.condition_defaults)
    # Intake-level conditions from form
    effective.update({
        "community_engagement": intake.community_engagement,
        "indigenous_engagement": intake.indigenous_engagement,
    })
    # Extra conditions from intake form
    effective.update(intake.conditions)

    kept: list[ResolvedTask] = []
    for task in tasks:
        if task.condition is None:
            kept.append(task)
        elif effective.get(task.condition, False):
            kept.append(task)
        else:
            logger.debug(
                "Filtered out task %s (condition=%s not met)", task.temp_id, task.condition
            )

    return kept, effective


def _validate_deps(tasks: list[ResolvedTask]) -> list[ResolvedTask]:
    """Prune depends_on refs that point to removed tasks. Log warnings, don't fail."""
    valid_ids = {t.temp_id for t in tasks}
    for task in tasks:
        pruned = [d for d in task.depends_on if d in valid_ids]
        if len(pruned) != len(task.depends_on):
            removed = set(task.depends_on) - set(pruned)
            logger.warning(
                "Task %s: pruned dangling deps: %s", task.temp_id, removed
            )
            task.depends_on = pruned
    return tasks


def _calculate_budget(intake: IntakeAnswers, rules: BudgetRules) -> BudgetCalculation:
    """Calculate budget based on intake costs and city budget rules."""
    gross = intake.construction_cost
    eligible = gross  # could apply exclusions in future
    rate = rules.contribution_rate
    art_contribution = eligible * rate
    reserve_rate = rules.maintenance_reserve_rate
    reserve = art_contribution * reserve_rate
    total = art_contribution + reserve

    return BudgetCalculation(
        contribution_rate=rate,
        cost_basis=rules.cost_basis,
        gross_cost=gross,
        eligible_cost=eligible,
        art_contribution=art_contribution,
        maintenance_reserve=reserve,
        maintenance_reserve_rate=reserve_rate,
        total=total,
    )


def resolve_template(intake: IntakeAnswers) -> ResolvedManifest:
    """
    Full resolution pipeline.

    1. Load base template
    2. Load city overlay
    3. Apply overrides (modify/add/remove)
    4. Resolve conditions (filter by intake answers)
    5. Validate dependencies (prune dangling refs)
    6. Calculate budget
    7. Return ResolvedManifest
    """
    # 1. Load base
    template = load_base_template()
    raw_tasks = template["tasks"]
    stages_raw = template["stages"]
    base_count = len(raw_tasks)

    # 2. Load overlay
    overlay = load_city_overlay(intake.municipality)

    # 3. Convert + apply overrides
    tasks = _tasks_to_resolved(raw_tasks)
    tasks = _apply_overrides(tasks, overlay)
    added_count = sum(1 for t in tasks if t.source == TaskSource.ADDED)

    # 4. Resolve conditions
    tasks, conditions_applied = _resolve_conditions(tasks, intake, overlay)
    removed_count = (base_count + added_count) - len(tasks)

    # 5. Validate deps
    tasks = _validate_deps(tasks)

    # 5b. Attach policy notes from the matrix store
    try:
        from .policy_matrix import get_policy_matrix_store

        pm_store = get_policy_matrix_store()
        notes_by_task = pm_store.get_all_notes_for_city_tasks(intake.municipality)
        for task in tasks:
            task_notes = notes_by_task.get(task.temp_id, [])
            if task_notes:
                task.policy_notes = task_notes
    except Exception:
        logger.debug("Policy matrix not available, skipping note attachment")

    # 6. Sort by stage, then by original order (temp_id is a proxy)
    tasks.sort(key=lambda t: (t.stage, t.temp_id))

    # 7. Calculate budget
    budget = _calculate_budget(intake, overlay.budget_rules)

    # Build stage info
    stage_counts: dict[int, int] = {}
    for t in tasks:
        stage_counts[t.stage] = stage_counts.get(t.stage, 0) + 1

    stages = [
        StageInfo(
            number=s["number"],
            name=s["name"],
            task_count=stage_counts.get(s["number"], 0),
        )
        for s in stages_raw
    ]

    return ResolvedManifest(
        tasks=tasks,
        stages=stages,
        municipality=intake.municipality,
        city_name=overlay.city_name,
        budget=budget,
        conditions_applied=conditions_applied,
        total_tasks=len(tasks),
        base_task_count=base_count,
        added_task_count=added_count,
        removed_task_count=removed_count,
    )
