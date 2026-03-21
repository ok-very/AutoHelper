"""Document generation endpoints."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from autohelper.config import get_settings
from autohelper.modules.images.report import generate_report
from autohelper.modules.images.thumbs import ensure_thumbnails
from .contexts import SubmissionReportRow, SubmissionReportContext
from .engine import get_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])

MANIFESTS_DIR = Path(__file__).resolve().parent.parent.parent / "gui" / "manifests"


class SubmissionReportRequest(BaseModel):
    manifest: str
    review_states: dict | None = None


def _load_manifest(manifest_id: str) -> dict:
    """Load manifest JSON by ID."""
    manifest_path = MANIFESTS_DIR / f"{manifest_id}.json"
    if not manifest_path.is_file():
        raise HTTPException(404, f"Manifest not found: {manifest_id}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _get_report_config(manifest: dict) -> tuple[int, int]:
    """Resolve thumbnail config: settings → manifest → defaults."""
    settings = get_settings()
    max_area = getattr(settings, "report_thumbnail_max_area", None)
    quality = getattr(settings, "report_thumbnail_quality", None)

    report_conf = manifest.get("report", {})
    if max_area is None:
        max_area = report_conf.get("thumbnailMaxArea", 15000)
    if quality is None:
        quality = report_conf.get("thumbnailQuality", 80)

    return int(max_area), int(quality)


@router.post("/submission-report")
async def submission_report(req: SubmissionReportRequest):
    """Generate an HTML submission report with thumbnails."""
    settings = get_settings()
    manifest = _load_manifest(req.manifest)

    # Generate report data (image dimensions, review state merge)
    rows = generate_report(req.manifest, settings.image_allowed_roots, req.review_states)

    # Get image roots from manifest, fall back to settings
    roots = manifest.get("dataSources", {}).get("imageBases", settings.image_allowed_roots)

    # Build tier lookup
    tiers = {}
    tier_labels = {}
    for tier in manifest.get("imagePipeline", {}).get("metricTiers", []):
        tiers[tier["id"]] = tier
        tier_labels[tier["id"]] = tier.get("label", tier["id"])

    # Generate thumbnails
    max_area, quality = _get_report_config(manifest)
    thumb_map = ensure_thumbnails(req.manifest, rows, roots, max_area, quality)

    # Build context rows
    context_rows = []
    for row in rows:
        # Compute tier print sizes
        tier_sizes = {}
        for tier_id, tier in tiers.items():
            pw = row.get(f"print_w_{tier_id}")
            ph = row.get(f"print_h_{tier_id}")
            if pw is not None and ph is not None:
                tier_sizes[tier_id] = (pw, ph)

        # Resolve DPI labels
        selected_dpis = row.get("selected_dpis", "")
        if isinstance(selected_dpis, str):
            dpi_list = [s.strip() for s in selected_dpis.split("|") if s.strip()]
        else:
            dpi_list = selected_dpis

        # Floor/category are now lists
        floor = row.get("floor", [])
        if isinstance(floor, str):
            floor = [floor] if floor else []
        category = row.get("category", [])
        if isinstance(category, str):
            category = [category] if category else []

        # Resolve floor/category labels from manifest assignment groups
        floor_group = manifest.get("assignmentGroups", {}).get("floor", {})
        floor_opts = {o["value"]: o for o in floor_group.get("options", [])}
        floor_labels = []
        for f in floor:
            opt = floor_opts.get(f)
            floor_labels.append(
                f"{opt['emoji']} {opt['label']}" if opt and opt.get("emoji") else (opt["label"] if opt else f)
            )

        cat_group = manifest.get("assignmentGroups", {}).get("category", {})
        cat_opts = {o["value"]: o for o in cat_group.get("options", [])}
        cat_labels = []
        for c in category:
            opt = cat_opts.get(c)
            cat_labels.append(opt["label"] if opt else c)

        context_rows.append(SubmissionReportRow(
            artist_name=row.get("artist_name") or "",
            title=row.get("title") or "",
            location_text=row.get("location_text") or "",
            image_path=row.get("image_path") or "",
            thumb_url=thumb_map.get(row.get("image_path") or ""),
            width_px=row.get("width_px"),
            height_px=row.get("height_px"),
            file_bytes=row.get("file_bytes"),
            floor=floor_labels,
            category=cat_labels,
            selected_dpis=dpi_list,
            rank=row.get("rank", 0),
            confirmed=row.get("confirmed", False),
            tiers=tier_sizes,
        ))

    context = SubmissionReportContext(
        manifest_id=req.manifest,
        manifest_name=manifest.get("name", req.manifest),
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        rows=context_rows,
        tier_labels=tier_labels,
    )

    engine = get_engine()
    return engine.render_to_response(
        "docs/submission_report.html",
        context.model_dump(),
    )


# ── Context Map ──────────────────────────────────────────────────────────────

@router.get("/context-map/{slug}")
async def get_context_map(slug: str) -> FileResponse:
    """Render a static context map for a test site and return the PNG.

    Usage: GET /api/documents/context-map/domus-st-georges
    """
    from autohelper.modules.documents.context_map.service import TEST_SITES, create_static_context_map
    from autohelper.modules.documents.context_map.types import ContextArtwork, ContextMapRequest

    site = next((s for s in TEST_SITES if s["slug"] == slug), None)
    if not site:
        slugs = [s["slug"] for s in TEST_SITES]
        raise HTTPException(status_code=404, detail=f"Unknown slug. Available: {slugs}")
    try:
        request = ContextMapRequest(
            project_slug=site["slug"],
            site_address=site["address"],
            site_label=site.get("site_label", ""),
            municipality=site.get("municipality", ""),
            context_artworks=[ContextArtwork(**a) for a in site["context_artworks"]],
        )
        result = await create_static_context_map(request)
        return FileResponse(result.output_path, media_type="image/png")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/context-map/test-sites")
async def get_test_sites() -> list[dict]:
    """Return the known BFA test sites with their context artworks."""
    from autohelper.modules.documents.context_map.service import TEST_SITES
    return TEST_SITES


# ── DOCX Templates ──────────────────────────────────────────────────────────


@router.get("/docx/templates")
async def list_docx_templates() -> list[dict]:
    """List available .docx templates with their merge fields."""
    from .docx_engine import list_templates
    return [
        {"key": t.key, "name": t.name, "fields": t.fields}
        for t in list_templates()
    ]


@router.get("/docx/templates/{template_key}")
async def get_docx_template(template_key: str) -> dict:
    """Get a single template's metadata and merge fields."""
    from .docx_engine import get_template
    info = get_template(template_key)
    if not info:
        raise HTTPException(status_code=404, detail=f"Template not found: {template_key}")
    return {"key": info.key, "name": info.name, "fields": info.fields}


# Legal letter → BFA task temp_id mapping (Stage 11 CLOSE-OUT)
LEGAL_LETTER_TASK_MAP = {
    "artwork_acceptance": "dry-11-3",     # Execute Letter of Acceptance (DocuSign)
    "transfer_of_title": "dry-11-4",      # Execute Transfer of Title (DocuSign)
    "statutory_declaration": "dry-11-5",   # Execute Statutory Declaration
}

# Municipality → required legal letters. Driven by policy matrix Stage 11 requirements.
# Artwork acceptance + transfer of title are universal.
# Statutory declaration is specific to municipalities with Section 219 covenant registration.
# Municipality → required legal letters, driven by city close-out checklists.
# Burnaby: Section 5.0 Security Release requires all three in Final Documentation Package.
# Vancouver: Section 219 covenant process requires all three + statutory declaration for registration.
# Default: all three until we have the specific city checklist saying otherwise.
MUNICIPALITY_LEGAL_LETTERS: dict[str, list[str]] = {
    "vancouver": ["artwork_acceptance", "transfer_of_title", "statutory_declaration"],
    "burnaby": ["artwork_acceptance", "transfer_of_title", "statutory_declaration"],
}
DEFAULT_LEGAL_LETTERS = ["artwork_acceptance", "transfer_of_title", "statutory_declaration"]


def _get_applicable_letters(municipality: str) -> list[str]:
    """Return legal letter template keys applicable for a municipality."""
    return MUNICIPALITY_LEGAL_LETTERS.get(municipality, DEFAULT_LEGAL_LETTERS)


@router.get("/docx/legal-letters/{project_id}")
async def get_project_legal_letters(project_id: str):
    """Return applicable legal letters for a project based on municipality policy."""
    from .docx_engine import build_project_context, get_template
    from autohelper.modules.projects.service import get_project

    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    applicable = _get_applicable_letters(project.municipality)
    ctx = build_project_context(project_id)

    letters = []
    for key in applicable:
        info = get_template(key)
        if not info:
            continue
        fields = [f for f in info.fields if f not in ("generated_at", "filename")]
        filled = sum(1 for f in fields if ctx.get(f))
        letters.append({
            "template_key": key,
            "template_name": info.name,
            "total_fields": len(fields),
            "filled_count": filled,
            "unfilled_count": len(fields) - filled,
        })

    return {
        "project_id": project_id,
        "municipality": project.municipality,
        "letters": letters,
    }


@router.get("/docx/preview/{project_id}/{template_key}")
async def preview_legal_letter(project_id: str, template_key: str):
    """Preview merge field status for a template + project without rendering."""
    from .docx_engine import build_project_context, get_template

    info = get_template(template_key)
    if not info:
        raise HTTPException(404, f"Template not found: {template_key}")

    try:
        ctx = build_project_context(project_id)
    except ValueError as e:
        raise HTTPException(404, str(e))

    fields = []
    for f in info.fields:
        if f in ("generated_at", "filename"):
            continue  # auto-filled at render time
        val = ctx.get(f)
        fields.append({"field": f, "value": val or None, "filled": bool(val)})

    filled = sum(1 for f in fields if f["filled"])
    return {
        "template_key": template_key,
        "template_name": info.name,
        "project_id": project_id,
        "total_fields": len(fields),
        "filled_count": filled,
        "unfilled_count": len(fields) - filled,
        "fields": fields,
    }


class DocxRenderRequest(BaseModel):
    template_key: str
    project_id: str | None = None
    context: dict[str, str] = {}


@router.post("/docx/render")
async def render_docx(req: DocxRenderRequest):
    """Render a .docx template with project context + optional overrides.

    If project_id is provided, auto-resolves context from intake + contact hub.
    Extra fields in `context` override or supplement the auto-resolved values.
    Returns the rendered .docx file.
    """
    from .docx_engine import render_template, build_project_context

    # Build context
    merge_context: dict[str, str] = {}
    project_label = ""
    if req.project_id:
        try:
            merge_context = build_project_context(req.project_id)
            project_label = merge_context.get("project_name", "")
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    # Override with explicit context
    merge_context.update(req.context)
    if not project_label:
        project_label = merge_context.get("project_name", merge_context.get("artwork_title", ""))

    try:
        result = render_template(
            template_key=req.template_key,
            context=merge_context,
            project_label=project_label,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return FileResponse(
        result.output_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=result.filename,
        headers={"X-Generated-At": result.generated_at, "X-Unfilled": ",".join(result.unfilled)},
    )


class DocxPipelineRequest(BaseModel):
    """Render template → convert to PDF → optionally attach to ClickUp task."""
    template_key: str
    project_id: str
    clickup_task_id: str | None = None
    context: dict[str, str] = {}


@router.post("/docx/pipeline")
async def docx_pipeline(req: DocxPipelineRequest):
    """Full pipeline: render .docx → PDF → optional ClickUp attachment.

    Returns metadata about the generated files and attachment status.
    """
    from .docx_engine import render_template, build_project_context, convert_to_pdf, legal_letter_output_dir

    # Build context from project
    merge_context: dict[str, str] = {}
    try:
        merge_context = build_project_context(req.project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    merge_context.update(req.context)
    project_label = merge_context.get("project_name", "")

    # Render DOCX — save to project's OneDrive Legal Letters folder
    out_dir = legal_letter_output_dir(project_label) if req.template_key in LEGAL_LETTER_TASK_MAP else None
    try:
        result = render_template(
            template_key=req.template_key,
            context=merge_context,
            project_label=project_label,
            output_dir=out_dir,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Convert to PDF
    try:
        pdf_path = convert_to_pdf(result.output_path)
    except Exception as e:
        logger.error("PDF conversion failed: %s", e)
        raise HTTPException(status_code=500, detail=f"PDF conversion failed: {e}")

    response = {
        "template_key": result.template_key,
        "docx_path": str(result.output_path),
        "pdf_path": str(pdf_path),
        "filename": result.filename,
        "pdf_filename": pdf_path.name,
        "generated_at": result.generated_at,
        "unfilled": result.unfilled,
        "attachment": None,
    }

    # ClickUp integration: attach PDF + create subtasks for unfilled fields
    from autohelper.config import get_settings
    from autohelper.modules.clickup.client import ClickUp
    from autohelper.modules.clickup.types import CreateTaskData

    settings = get_settings()
    token = getattr(settings, "clickup_token", "")

    # Auto-resolve ClickUp task ID if not provided
    clickup_task_id = req.clickup_task_id
    if not clickup_task_id and token and req.template_key in LEGAL_LETTER_TASK_MAP:
        try:
            clickup_task_id = await _resolve_legal_letter_task_id(
                req.project_id, req.template_key, token
            )
        except Exception as e:
            logger.warning("Could not auto-resolve ClickUp task: %s", e)

    if clickup_task_id and token:
        try:
            async with ClickUp(token) as cu:
                # Attach PDF
                att = await cu.attachments.upload(clickup_task_id, str(pdf_path), pdf_path.name)
                response["attachment"] = att
                logger.info("Attached %s to task %s", pdf_path.name, clickup_task_id)

                # Create subtasks for unfilled fields
                if result.unfilled:
                    from autohelper.modules.projects.service import get_project
                    project = get_project(req.project_id)
                    list_id = project.clickup_list_id if project else None
                    if list_id:
                        subtasks = []
                        for field in result.unfilled:
                            if field in ("generated_at", "filename"):
                                continue
                            label = field.replace("_", " ").title()
                            sub = await cu.tasks.create(list_id, CreateTaskData(
                                name=f"Resolve: {label}",
                                parent=clickup_task_id,
                                tags=["pending_merge_field"],
                            ))
                            subtasks.append({"id": sub.id, "name": sub.name})
                            await asyncio.sleep(0.15)
                        response["subtasks_created"] = subtasks
                        logger.info("Created %d subtasks for unfilled fields", len(subtasks))
        except Exception as e:
            logger.error("ClickUp integration failed: %s", e)
            response["clickup_error"] = str(e)

    return response


async def _resolve_legal_letter_task_id(
    project_id: str, template_key: str, token: str
) -> str | None:
    """Find the ClickUp task ID for a legal letter by matching task name."""
    from autohelper.modules.projects.service import get_project
    from autohelper.modules.projects.template_resolver import resolve_template
    from autohelper.modules.clickup.client import ClickUp

    project = get_project(project_id)
    if not project or not project.clickup_list_id:
        return None

    temp_id = LEGAL_LETTER_TASK_MAP.get(template_key)
    if not temp_id:
        return None

    manifest = resolve_template(project.intake)
    task_def = next((t for t in manifest.tasks if t.temp_id == temp_id), None)
    if not task_def:
        return None

    target = task_def.name.strip().lower()
    async with ClickUp(token) as cu:
        tasks = await cu.tasks.list_all(project.clickup_list_id, include_closed=True)
    return next((t.id for t in tasks if t.name.strip().lower() == target), None)
