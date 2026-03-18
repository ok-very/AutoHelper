"""BFA To Do List API router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from autohelper.shared.logging import get_logger

from . import service

logger = get_logger(__name__)

router = APIRouter(prefix="/api/bfa-todo", tags=["bfa-todo"])


@router.get("/status")
async def get_status() -> dict[str, Any]:
    """Pipeline status (project count, last render, output availability)."""
    return service.get_status()


@router.get("/preambles")
async def list_preambles() -> list[dict[str, Any]]:
    """List preamble blocks (overview + proposals)."""
    return service.list_preambles()


@router.get("/preambles/{uid}/html", response_class=HTMLResponse)
async def get_preamble_html(uid: str) -> HTMLResponse:
    """Return self-contained HTML for a preamble block (for iframe embedding)."""
    html = service.get_preamble_html(uid)
    if not html:
        raise HTTPException(404, f"Preamble {uid} not found")
    return HTMLResponse(html)


@router.put("/preambles/{uid}/sections/{section_name}")
async def update_preamble_section(uid: str, section_name: str, req: UpdateSectionContentRequest) -> dict[str, Any]:
    """Save a single preamble section edit."""
    result = service.update_project_section(uid, section_name, req.html)
    if result is None:
        raise HTTPException(404, f"Preamble {uid} not found")
    return result


@router.get("/projects")
async def list_projects() -> list[dict[str, Any]]:
    """List all projects (summary)."""
    return service.list_projects()


@router.get("/projects/{uid}")
async def get_project(uid: str) -> dict[str, Any]:
    """Get single project detail."""
    project = service.get_project(uid)
    if not project:
        raise HTTPException(404, f"Project {uid} not found")
    return project


@router.get("/projects/{uid}/html", response_class=HTMLResponse)
async def get_project_html(uid: str) -> HTMLResponse:
    """Return self-contained HTML for a project (for iframe embedding)."""
    html = service.get_project_html(uid)
    if not html:
        raise HTTPException(404, f"Project {uid} not found")
    return HTMLResponse(html)


@router.post("/render")
async def render() -> dict[str, Any]:
    """Run pipeline: load YAML -> render HTML + JSON + GDocs payloads."""
    try:
        return service.render_pipeline()
    except Exception as e:
        logger.error("Render failed: %s", e, exc_info=True)
        raise HTTPException(500, f"Render failed: {e}")


class ImportExcelRequest(BaseModel):
    filepath: str


@router.post("/import-excel")
async def import_excel(req: ImportExcelRequest) -> dict[str, Any]:
    """Import Monday.com Excel, return match report."""
    try:
        return service.import_excel(req.filepath)
    except FileNotFoundError:
        raise HTTPException(404, f"File not found: {req.filepath}")
    except Exception as e:
        logger.error("Excel import failed: %s", e, exc_info=True)
        raise HTTPException(500, f"Import failed: {e}")


class UpdateProjectRequest(BaseModel):
    """Editable fields for a BFA project."""
    next_steps: str | None = None
    contacts_text: str | None = None
    artists_text: str | None = None
    phase: str | None = None
    owner_team: str | None = None


@router.put("/projects/{uid}")
async def update_project(uid: str, req: UpdateProjectRequest) -> dict[str, Any]:
    """Update editable fields on a project."""
    changes = {k: v for k, v in req.model_dump().items() if v is not None}
    if not changes:
        raise HTTPException(400, "No changes provided")
    result = service.update_project(uid, changes)
    if result is None:
        raise HTTPException(404, f"Project {uid} not found")
    return result


class UpdateSectionsRequest(BaseModel):
    """Edited section HTML from contenteditable iframe."""
    sections: dict[str, str]  # section_name → innerHTML
    header: str | None = None


@router.put("/projects/{uid}/sections")
async def update_sections(uid: str, req: UpdateSectionsRequest) -> dict[str, Any]:
    """Save contenteditable section edits back to YAML."""
    if not req.sections and req.header is None:
        raise HTTPException(400, "No changes provided")
    result = service.update_project_sections(uid, req.sections, req.header)
    if result is None:
        raise HTTPException(404, f"Project {uid} not found")
    return result


class UpdateSectionContentRequest(BaseModel):
    """Single section HTML from composition view."""
    html: str


@router.put("/projects/{uid}/sections/{section_name}")
async def update_section(uid: str, section_name: str, req: UpdateSectionContentRequest) -> dict[str, Any]:
    """Save a single section edit from the composition view."""
    result = service.update_project_section(uid, section_name, req.html)
    if result is None:
        raise HTTPException(404, f"Project {uid} not found")
    return result


class UpdatePhaseRequest(BaseModel):
    """Phase selection from composition view dropdown."""
    phase: str


@router.put("/projects/{uid}/phase")
async def update_phase(uid: str, req: UpdatePhaseRequest) -> dict[str, Any]:
    """Update project phase via dropdown selection."""
    result = service.update_project_phase(uid, req.phase)
    if result is None:
        raise HTTPException(404, f"Project {uid} not found")
    return result


class ImportHtmlRequest(BaseModel):
    path: str = "C:/Users/Neal/dev/BFA-todo/data"


@router.post("/import-html")
async def import_html(req: ImportHtmlRequest) -> dict[str, Any]:
    """Import BFA data — auto-detects file (raw HTML) vs directory (YAML)."""
    import os
    try:
        if os.path.isfile(req.path):
            return service.import_from_html_file(req.path)
        else:
            return service.import_from_html_dir(req.path)
    except FileNotFoundError:
        raise HTTPException(404, f"Path not found: {req.path}")
    except Exception as e:
        logger.error("Import failed: %s", e, exc_info=True)
        raise HTTPException(500, f"Import failed: {e}")


class DeployRequest(BaseModel):
    doc_id: str


class DeploySelectedRequest(BaseModel):
    doc_id: str
    uids: list[str]


@router.post("/deploy")
async def deploy(req: DeployRequest) -> dict[str, Any]:
    """Push GDocs injection payloads to Google Docs."""
    try:
        return await service.deploy_to_gdocs(req.doc_id)
    except Exception as e:
        logger.error("Deploy failed: %s", e, exc_info=True)
        raise HTTPException(500, f"Deploy failed: {e}")


@router.post("/deploy-selected")
async def deploy_selected(req: DeploySelectedRequest) -> dict[str, Any]:
    """Deploy specific project UIDs to GDocs."""
    try:
        return await service.deploy_selected(req.doc_id, req.uids)
    except Exception as e:
        logger.error("Deploy selected failed: %s", e, exc_info=True)
        raise HTTPException(500, f"Deploy failed: {e}")
