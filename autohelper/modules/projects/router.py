"""Projects module API router."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .types import CityOverlay, IntakeAnswers, PolicyMatrixData, PolicyTopic, ProjectRecord, ResolvedManifest, CitySummary
from . import service

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("/cities", response_model=list[CitySummary])
async def list_cities() -> list[CitySummary]:
    """List available city configurations."""
    return service.list_cities()


@router.get("/cities/{city_id}")
async def get_city(city_id: str) -> CityOverlay:
    """Get full city overlay config."""
    try:
        return service.get_city(city_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"City not found: {city_id}") from e


@router.post("/preview", response_model=ResolvedManifest)
async def preview_resolution(intake: IntakeAnswers) -> ResolvedManifest:
    """Dry-run template resolution without creating a project."""
    try:
        return service.preview_resolution(intake)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ── Policy matrix endpoints (must come before /{project_id} routes) ───


class EntryUpdate(BaseModel):
    city_id: str
    topic_id: str
    text: str


class TopicsUpdate(BaseModel):
    topics: list[PolicyTopic]


class ImportRequest(BaseModel):
    path: str


@router.get("/policy-matrix", response_model=PolicyMatrixData)
async def get_policy_matrix() -> PolicyMatrixData:
    """Get full policy matrix."""
    return service.get_policy_matrix()


@router.put("/policy-matrix", response_model=PolicyMatrixData)
async def save_policy_matrix(data: PolicyMatrixData) -> PolicyMatrixData:
    """Save full policy matrix."""
    service.save_policy_matrix(data)
    return data


@router.put("/policy-matrix/topics")
async def update_topics(body: TopicsUpdate) -> dict:
    """Update topics only (reorder, rename, map)."""
    service.update_policy_topics(body.topics)
    return {"ok": True}


@router.put("/policy-matrix/entry")
async def update_entry(body: EntryUpdate) -> dict:
    """Update a single cell."""
    service.update_policy_entry(body.city_id, body.topic_id, body.text)
    return {"ok": True}


@router.post("/policy-matrix/import", response_model=PolicyMatrixData)
async def import_policy_matrix(body: ImportRequest) -> PolicyMatrixData:
    """Re-import from xlsx path."""
    try:
        return service.import_policy_matrix(body.path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ── Project CRUD ──────────────────────────────────────────────────


@router.get("", response_model=list[ProjectRecord])
async def list_projects() -> list[ProjectRecord]:
    """List all projects."""
    return service.list_projects()


@router.post("", response_model=ProjectRecord)
async def create_project(intake: IntakeAnswers) -> ProjectRecord:
    """Create a new draft project from intake answers."""
    try:
        return service.create_project(intake)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{project_id}", response_model=ProjectRecord)
async def get_project(project_id: str) -> ProjectRecord:
    """Get project detail."""
    project = service.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/{project_id}/provision", response_model=ProjectRecord)
async def provision_project(project_id: str) -> ProjectRecord:
    """Create ClickUp list and tasks for a draft project."""
    try:
        return await service.provision_project(project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{project_id}/status")
async def project_status(project_id: str) -> dict:
    """Get ClickUp task status for a provisioned project."""
    project = service.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.clickup_list_id:
        return {"status": project.status.value, "tasks": []}
    # Return basic status — full ClickUp polling can be added later
    return {
        "status": project.status.value,
        "clickup_list_id": project.clickup_list_id,
        "resolved_task_count": project.resolved_task_count,
    }


@router.delete("/{project_id}")
async def delete_project(project_id: str) -> dict:
    """Delete a draft project."""
    try:
        deleted = service.delete_project(project_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"deleted": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
