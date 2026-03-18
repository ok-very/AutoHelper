"""
Import manifest schemas for autoart → AutoHelper → ClickUp handoff.

The manifest describes a batch of tasks to create/update in ClickUp,
with support for parent-child hierarchy and custom field values.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ManifestCustomField(BaseModel):
    """A custom field value to set on a task."""

    field_id: str
    value: Any
    source_field: str | None = None


class ManifestTask(BaseModel):
    """A single task in the import manifest."""

    temp_id: str
    name: str
    description: str | None = None
    status: str | None = None
    parent_temp_id: str | None = None
    custom_fields: list[ManifestCustomField] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    is_milestone: bool = False
    email_template_key: str | None = None
    stage: int | None = None
    stage_name: str | None = None


class ManifestTarget(BaseModel):
    """Where to create tasks in ClickUp."""

    workspace_id: str
    space_id: str
    folder_id: str | None = None
    list_id: str


class ImportManifest(BaseModel):
    """
    Complete import manifest for a batch of tasks.

    Sent from autoart backend via the poller command system
    or directly via POST /clickup/execute-manifest.
    """

    version: str = "1.0"
    session_id: str = ""
    source: Literal["monday", "csv", "template"] = "monday"
    target: ManifestTarget
    tasks: list[ManifestTask]


# ── Execution Result ──────────────────────────────────────────────────────


class TaskResult(BaseModel):
    """Result for a single task in the manifest."""

    temp_id: str
    clickup_id: str | None = None
    success: bool
    error: str | None = None


class ManifestExecutionResult(BaseModel):
    """Result of executing an import manifest."""

    session_id: str
    total: int
    created: int = 0
    updated: int = 0
    failed: int = 0
    id_map: dict[str, str] = Field(default_factory=dict)
    task_results: list[TaskResult] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
