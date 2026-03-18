"""Document generation endpoints."""

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
