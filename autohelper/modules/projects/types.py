"""Pydantic models for the projects module."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProjectType(str, Enum):
    """Type of public art project."""

    PRIVATE_DEVELOPMENT = "private_development"
    CIVIC = "civic"
    COMMUNITY = "community"


class ProjectStatus(str, Enum):
    """Lifecycle status of a project."""

    DRAFT = "draft"
    PROVISIONING = "provisioning"
    PROVISIONED = "provisioned"
    ACTIVE = "active"
    COMPLETED = "completed"


# ── Intake ────────────────────────────────────────────────────────


class IntakeAnswers(BaseModel):
    """Answers collected from the project intake wizard."""

    municipality: str
    project_type: ProjectType = ProjectType.PRIVATE_DEVELOPMENT
    project_name: str
    developer_name: str | None = None
    neighbourhood: str | None = None
    construction_cost: float = 0.0
    unit_count: int | None = None
    floor_area_sqm: float | None = None
    requires_rezoning: bool = False
    community_engagement: bool = False
    indigenous_engagement: bool = False
    conditions: dict[str, bool] = Field(default_factory=dict)


# ── Budget ────────────────────────────────────────────────────────


class BudgetCalculation(BaseModel):
    """Computed budget breakdown."""

    contribution_rate: float
    cost_basis: str
    gross_cost: float
    eligible_cost: float
    art_contribution: float
    maintenance_reserve: float
    maintenance_reserve_rate: float
    total: float


# ── Resolved template ────────────────────────────────────────────


class TaskSource(str, Enum):
    """Where a resolved task came from."""

    BASE = "base"
    OVERLAY = "overlay"
    ADDED = "added"


class ResolvedTask(BaseModel):
    """A single task after template resolution."""

    temp_id: str
    name: str
    stage: int
    is_milestone: bool = False
    parent_temp_id: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    email_template_key: str | None = None
    condition: str | None = None
    source: TaskSource = TaskSource.BASE
    policy_notes: list[PolicyNote] = Field(default_factory=list)


class StageInfo(BaseModel):
    """Stage metadata."""

    number: int
    name: str
    task_count: int = 0


class ResolvedManifest(BaseModel):
    """Fully resolved project template."""

    tasks: list[ResolvedTask]
    stages: list[StageInfo]
    municipality: str
    city_name: str
    budget: BudgetCalculation | None = None
    conditions_applied: dict[str, bool] = Field(default_factory=dict)
    total_tasks: int = 0
    base_task_count: int = 0
    added_task_count: int = 0
    removed_task_count: int = 0
    phase_field_id: str | None = None
    phase_options: dict[str, str] = Field(default_factory=dict)


# ── City config summary ──────────────────────────────────────────


class CitySummary(BaseModel):
    """Summary of a city overlay for listing."""

    city_id: str
    city_name: str
    policy_version: str
    contribution_rate: float
    task_override_count: int


# ── Project record ────────────────────────────────────────────────


class ProjectRecord(BaseModel):
    """Persisted project record."""

    id: str
    project_name: str
    developer_name: str | None = None
    municipality: str
    city_name: str
    project_type: ProjectType = ProjectType.PRIVATE_DEVELOPMENT
    intake: IntakeAnswers
    budget: BudgetCalculation | None = None
    resolved_task_count: int = 0
    clickup_list_id: str | None = None
    clickup_folder_id: str | None = None
    clickup_workspace_id: str | None = None
    status: ProjectStatus = ProjectStatus.DRAFT
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    provisioned_at: str | None = None


# ── City overlay (full schema) ────────────────────────────────────


class BudgetRules(BaseModel):
    """City budget calculation rules."""

    contribution_rate: float = 0.01
    cost_basis: str = "construction"
    excludes: list[str] = Field(default_factory=list)
    maintenance_reserve_rate: float = 0.0
    maintenance_reserve_mandatory: bool = False


class CityThresholds(BaseModel):
    """City eligibility thresholds."""

    residential_units_min: int | None = None
    commercial_area_sqm_min: float | None = None
    requires_rezoning: bool = False
    applicable_zones: list[str] = Field(default_factory=list)
    neighbourhoods: list[str] = Field(default_factory=list)


class CityConstraints(BaseModel):
    """City-specific constraints."""

    artist_cannot_be_project_team: bool = False
    barred_roles: list[str] = Field(default_factory=list)


class TaskOverrideAdd(BaseModel):
    """Task to add via overlay."""

    temp_id: str
    name: str
    stage: int
    depends_on: list[str] = Field(default_factory=list)
    condition: str | None = None
    is_milestone: bool = False
    parent_temp_id: str | None = None
    email_template_key: str | None = None


class TaskOverride(BaseModel):
    """A single task override entry."""

    action: str  # "modify" or "add"
    temp_id: str | None = None
    changes: dict[str, Any] | None = None
    task: TaskOverrideAdd | None = None


# ── Policy matrix ─────────────────────────────────────────────────


class PolicyTopic(BaseModel):
    """A row in the policy matrix — a deliverable topic."""

    id: str
    label: str
    stage: int
    maps_to: list[str] = Field(default_factory=list)
    order: int = 0


class PolicyMatrixData(BaseModel):
    """Full policy matrix: topics + city entries."""

    version: str = "1.0"
    topics: list[PolicyTopic] = Field(default_factory=list)
    entries: dict[str, dict[str, str]] = Field(default_factory=dict)
    city_names: dict[str, str] = Field(default_factory=dict)


class PolicyNote(BaseModel):
    """A single policy note attached to a resolved task."""

    topic: str
    text: str


# ── City overlay (full schema) ────────────────────────────────────


class CityOverlay(BaseModel):
    """Full city overlay configuration."""

    city_id: str
    city_name: str
    policy_version: str = "current"
    policy_source: str | None = None
    budget_rules: BudgetRules = Field(default_factory=BudgetRules)
    thresholds: CityThresholds = Field(default_factory=CityThresholds)
    constraints: CityConstraints = Field(default_factory=CityConstraints)
    condition_defaults: dict[str, bool] = Field(default_factory=dict)
    task_overrides: list[TaskOverride] = Field(default_factory=list)
    task_removals: list[str] = Field(default_factory=list)
