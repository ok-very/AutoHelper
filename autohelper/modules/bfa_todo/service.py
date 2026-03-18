"""BFA To Do List service — orchestrates pipeline operations."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autohelper.shared.logging import get_logger
from autohelper.shared.paths import data_dir

from .google_client import GoogleDocsClient, GoogleClientError
from .pipeline import config as pipeline_config
from .pipeline.store import (
    load_all_projects,
    load_index,
    load_project,
    save_aliases,
    save_index,
    save_project,
    load_aliases,
)

logger = get_logger(__name__)

# Source data for seeding
_BFA_TODO_SOURCE = Path("C:/Users/Neal/dev/BFA-todo/data")


def _ensure_data_dir() -> Path:
    """Ensure the bfa_todo data directory exists."""
    d = pipeline_config.DATA_DIR
    d.mkdir(parents=True, exist_ok=True)
    pipeline_config.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    return d


def seed_if_empty() -> bool:
    """Copy seed data from BFA-todo if the data directory is empty.

    Returns True if seeding was performed.
    """
    _ensure_data_dir()
    index_path = pipeline_config.DATA_DIR / "index.yaml"
    if index_path.exists():
        return False

    if not _BFA_TODO_SOURCE.exists():
        logger.warning("BFA-todo source not found at %s, skipping seed", _BFA_TODO_SOURCE)
        return False

    # Copy index.yaml
    src_index = _BFA_TODO_SOURCE / "index.yaml"
    if src_index.exists():
        shutil.copy2(str(src_index), str(index_path))

    # Copy aliases.yaml
    src_aliases = _BFA_TODO_SOURCE / "aliases.yaml"
    if src_aliases.exists():
        shutil.copy2(str(src_aliases), str(pipeline_config.ALIASES_FILE))

    # Copy project files
    src_projects = _BFA_TODO_SOURCE / "projects"
    if src_projects.exists():
        for f in src_projects.glob("*.yaml"):
            shutil.copy2(str(f), str(pipeline_config.PROJECTS_DIR / f.name))

    logger.info("Seeded BFA To Do data from %s", _BFA_TODO_SOURCE)
    return True


def import_from_html_dir(path: str) -> dict[str, Any]:
    """Force re-import YAML data from a BFA HTML source directory."""
    src = Path(path)
    if not src.exists():
        raise FileNotFoundError(f"Directory not found: {path}")

    _ensure_data_dir()

    # Copy index.yaml
    src_index = src / "index.yaml"
    if src_index.exists():
        shutil.copy2(str(src_index), str(pipeline_config.DATA_DIR / "index.yaml"))

    # Copy aliases.yaml
    src_aliases = src / "aliases.yaml"
    if src_aliases.exists():
        shutil.copy2(str(src_aliases), str(pipeline_config.ALIASES_FILE))

    # Copy project files
    src_projects = src / "projects"
    count = 0
    if src_projects.exists():
        for f in src_projects.glob("*.yaml"):
            shutil.copy2(str(f), str(pipeline_config.PROJECTS_DIR / f.name))
            count += 1

    logger.info("Imported %d project files from %s", count, path)
    return {"project_count": count, "source": path}


def import_from_html_file(filepath: str) -> dict[str, Any]:
    """Import from a raw Google Docs HTML export through the full pipeline.

    Parses the HTML, extracts gdocs CSS, processes projects with StyleResolver,
    saves YAML + CSS to disk, and runs a full render.
    """
    src = Path(filepath)
    if not src.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    from .pipeline.importer import import_document
    from .pipeline.processor import process_project
    from .pipeline.style_resolver import StyleResolver
    from .pipeline.renderer import render_all

    _ensure_data_dir()

    # Parse HTML → raw project blocks + gdocs CSS
    projects, gdocs_css = import_document(filepath)

    # Process each project (clean, classify, compute runs)
    resolver = StyleResolver(gdocs_css)
    processed = []
    for p in projects:
        processed.append(process_project(p, resolver=resolver))

    # Save YAML (runs are stripped by save_project — that's correct,
    # they're recomputed at render time from .html + gdocs CSS)
    for p in processed:
        save_project(p)
    save_index(processed)

    # Persist gdocs CSS so render_pipeline() and render_one() can reload it
    pipeline_config.ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    (pipeline_config.ASSETS_DIR / "gdocs.css").write_text(gdocs_css, encoding="utf-8")

    # Run full render to produce canonical.css, index_pasteable.html, etc.
    render_all(processed, gdocs_css)

    project_count = sum(1 for p in processed if p.get("type") == "project")
    logger.info("Imported %d projects from HTML file %s", project_count, filepath)
    return {"project_count": project_count, "source": filepath}


def get_status() -> dict[str, Any]:
    """Return pipeline status summary."""
    _ensure_data_dir()
    seed_if_empty()

    index = load_index()
    project_count = index.get("project_count", 0)

    # Check for rendered output
    site_dir = pipeline_config.SITE_DIR
    html_exists = (site_dir / "index.html").exists()
    json_exists = (site_dir / "projects.json").exists()
    gdocs_exists = (site_dir / "gdocs_inject.json").exists()

    last_render = None
    if html_exists:
        mtime = (site_dir / "index.html").stat().st_mtime
        last_render = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

    return {
        "project_count": project_count,
        "last_render": last_render,
        "has_html": html_exists,
        "has_json": json_exists,
        "has_gdocs": gdocs_exists,
    }


def list_projects() -> list[dict[str, Any]]:
    """Return summary list of all projects."""
    from .pipeline.processor import derive_metadata

    _ensure_data_dir()
    seed_if_empty()

    projects = load_all_projects()
    summaries = []
    for p in projects:
        if p.get("type") not in ("project",):
            continue
        meta = derive_metadata(p)
        summaries.append({
            "uid": p["uid"],
            "slug": p.get("slug", ""),
            "client": p.get("fields", {}).get("client", "TBC"),
            "project_name": p.get("fields", {}).get("project_name", "TBC"),
            "city": p.get("fields", {}).get("city", "TBC"),
            "phase": meta["bfa_phase_canonical"],
            "owner_team": p.get("fields", {}).get("owner_team", "BFA"),
            "status": p.get("status", "active"),
        })
    return summaries


def get_project(uid: str) -> dict[str, Any] | None:
    """Return a single project's full data with inline_html, derived metadata,
    and section_meta for the composition view."""
    from .pipeline.processor import derive_metadata, get_section_meta

    _ensure_data_dir()
    project = load_project(uid)
    if not project:
        return None

    # Compute inline_html for each section so the frontend can render
    # a faithful preview (bold, highlight, indentation) without running
    # the full render pipeline first.
    _enrich_inline_html(project)

    # Derived metadata (phase, contacts, artists, next_steps) from sections
    project["derived"] = derive_metadata(project)

    # Editability metadata per section for the composition view
    project["section_meta"] = get_section_meta(project.get("sections", {}))

    # Header inline_html for composition view
    header = project.get("header", {})
    header_text = header.get("text", "")
    if header_text and "inline_html" not in header:
        escaped = (header_text.replace("&", "&amp;")
                   .replace("<", "&lt;").replace(">", "&gt;"))
        header["inline_html"] = (
            f'<h3><span style="font-weight:700;text-decoration:underline;'
            f'font-size:11pt">{escaped}</span></h3>'
        )

    return project


def _enrich_inline_html(project: dict[str, Any]) -> None:
    """Compute inline_html for sections that have raw html but no inline_html.

    Uses gdocs CSS from disk (if available) so class-based styles
    (bold, highlight, etc.) resolve the same as the full render pipeline.
    """
    from .pipeline.style_resolver import StyleResolver, walk_html_for_runs, runs_to_inline_html

    gdocs_css = ""
    gdocs_css_path = pipeline_config.ASSETS_DIR / "gdocs.css"
    if gdocs_css_path.exists():
        gdocs_css = gdocs_css_path.read_text(encoding="utf-8")

    resolver = StyleResolver(gdocs_css)
    for sec_data in project.get("sections", {}).values():
        html = sec_data.get("html", "")
        if html.strip() and "inline_html" not in sec_data:
            runs = walk_html_for_runs(html, resolver)
            sec_data["inline_html"] = runs_to_inline_html(runs)


def get_project_html(uid: str) -> str | None:
    """Return fully-inlined HTML for a single project via the render pipeline.

    Uses the same template + premailer path as the full site render so the
    iframe preview matches index_pasteable.html exactly.
    """
    _ensure_data_dir()
    project = load_project(uid)
    if not project or project.get("type") != "project":
        return None

    from .pipeline.renderer import render_one

    return render_one(project)


def update_project(uid: str, changes: dict[str, Any]) -> dict[str, Any] | None:
    """Update editable fields on a project and persist to YAML."""
    _ensure_data_dir()
    project = load_project(uid)
    if not project:
        return None

    fields = project.get("fields", {})
    sections = project.get("sections", {})

    # Map editable keys to their storage locations
    field_keys = {"contacts_text", "artists_text", "owner_team"}
    section_keys = {"next_steps", "governance", "milestones", "fabrication"}

    for key, value in changes.items():
        if key == "phase":
            project["bfa_phase_canonical"] = value
        elif key in field_keys:
            fields[key] = value
        elif key in section_keys:
            if key not in sections:
                sections[key] = {}
            sections[key]["text"] = value
        else:
            fields[key] = value

    project["fields"] = fields
    project["sections"] = sections
    save_project(project)

    return {
        "uid": uid,
        "updated": list(changes.keys()),
    }


def _html_to_text(html: str) -> str:
    """Strip tags and decode entities to plain text."""
    from lxml import html as lxml_html
    try:
        doc = lxml_html.fromstring(f"<div>{html}</div>")
        return doc.text_content().strip()
    except Exception:
        import re
        return re.sub(r"<[^>]+>", "", html).strip()


def update_project_sections(
    uid: str,
    section_htmls: dict[str, str],
    header_html: str | None = None,
) -> dict[str, Any] | None:
    """Update section HTML from contenteditable edits and persist to YAML.

    Recomputes plain text from the edited HTML so downstream consumers
    (GDocs export, next_steps parser) stay in sync.
    """
    _ensure_data_dir()
    project = load_project(uid)
    if not project:
        return None

    sections = project.get("sections", {})
    for sec_name, html in section_htmls.items():
        if sec_name in sections:
            sections[sec_name]["html"] = html
            sections[sec_name]["text"] = _html_to_text(html)

    if header_html is not None:
        project["header"]["html"] = header_html
        project["header"]["text"] = _html_to_text(header_html)

    project["sections"] = sections
    save_project(project)

    return {"uid": uid, "updated_sections": list(section_htmls.keys())}


def update_project_section(
    uid: str,
    section_name: str,
    html: str,
) -> dict[str, Any] | None:
    """Update a single section's HTML and persist to YAML.

    Used by the composition view for per-section saves.
    Returns the updated project with re-enriched inline_html.
    """
    from .pipeline.processor import derive_metadata, get_section_meta

    _ensure_data_dir()
    project = load_project(uid)
    if not project:
        return None

    sections = project.get("sections", {})
    if section_name not in sections:
        # Allow creating new sections (e.g. adding next_steps to a project that didn't have them)
        sections[section_name] = {}

    sections[section_name]["html"] = html
    sections[section_name]["text"] = _html_to_text(html)
    project["sections"] = sections
    save_project(project)

    # Re-enrich and return full project for the composition view
    _enrich_inline_html(project)
    project["derived"] = derive_metadata(project)
    project["section_meta"] = get_section_meta(sections)

    return project


def update_project_phase(uid: str, phase: str) -> dict[str, Any] | None:
    """Update a project's phase via dropdown selection.

    Updates both the bfa_phase section and the derived canonical phase.
    """
    from .pipeline.processor import derive_metadata, get_section_meta

    _ensure_data_dir()
    project = load_project(uid)
    if not project:
        return None

    sections = project.get("sections", {})
    if "bfa_phase" not in sections:
        sections["bfa_phase"] = {}

    sections["bfa_phase"]["text"] = phase
    sections["bfa_phase"]["html"] = f'<p><strong>Project Status:</strong> {phase}</p>'
    project["sections"] = sections
    # Keep legacy key in sync during migration
    project["bfa_phase_canonical"] = phase
    save_project(project)

    _enrich_inline_html(project)
    project["derived"] = derive_metadata(project)
    project["section_meta"] = get_section_meta(sections)

    return project


def render_pipeline() -> dict[str, Any]:
    """Run the render pipeline: load YAML -> render HTML + JSON + GDocs payloads."""
    from .pipeline.renderer import render_all
    from .pipeline.style_resolver import StyleResolver

    _ensure_data_dir()
    seed_if_empty()

    projects = load_all_projects(include_archived=False)
    if not projects:
        return {"error": "No projects found", "outputs": {}}

    # Load gdocs CSS from disk (persisted during HTML import)
    gdocs_css = ""
    gdocs_css_path = pipeline_config.ASSETS_DIR / "gdocs.css"
    if gdocs_css_path.exists():
        gdocs_css = gdocs_css_path.read_text(encoding="utf-8")

    html_path, pasteable_path, json_path, gdocs_path = render_all(projects, gdocs_css)

    return {
        "project_count": len([p for p in projects if p.get("type") == "project"]),
        "outputs": {
            "html": html_path,
            "pasteable": pasteable_path,
            "json": json_path,
            "gdocs": gdocs_path,
        },
    }


def import_excel(filepath: str) -> dict[str, Any]:
    """Import a Monday.com Excel export and return match report."""
    from .pipeline.excel_importer import import_excel as _import_excel
    from .pipeline.matcher import match
    from .pipeline.differ import diff_matched, diff_rollups

    _ensure_data_dir()
    seed_if_empty()

    # Parse Excel
    excel_rows = _import_excel(filepath)

    # Load existing data
    projects = load_all_projects(include_archived=False)
    aliases = load_aliases()

    # Match
    match_report = match(excel_rows, projects, aliases)

    # Diff matched pairs
    yaml_by_uid = {p["uid"]: p for p in projects if p.get("type") == "project"}
    diff_report = diff_matched(match_report["matched"], yaml_by_uid)
    rollup_diffs = diff_rollups(match_report.get("rollup_groups", []), yaml_by_uid)

    return {
        "excel_row_count": len(excel_rows),
        "matched": len(match_report["matched"]),
        "new_in_excel": len(match_report["new_in_excel"]),
        "pipeline_only": len(match_report["pipeline_only"]),
        "ambiguous": len(match_report["ambiguous"]),
        "field_changes": diff_report["stats"]["total_changes"],
        "match_report": match_report,
        "diff_report": diff_report,
        "rollup_diffs": rollup_diffs,
    }


async def _deploy_payloads(
    doc_id: str, payloads: list[dict[str, Any]]
) -> dict[str, Any]:
    """Shared deployment logic: resolve anchors + push to Google Docs."""
    client = GoogleDocsClient()

    try:
        doc = await client.get_document(doc_id)
    except GoogleClientError as e:
        return {"error": str(e)}

    # Build flat text index for anchor lookup
    doc_text = ""
    for element in doc.get("body", {}).get("content", []):
        paragraph = element.get("paragraph")
        if paragraph:
            for el in paragraph.get("elements", []):
                text_run = el.get("textRun")
                if text_run:
                    doc_text += text_run.get("content", "")

    deployed: list[str] = []
    errors: list[dict[str, str]] = []

    for payload in payloads:
        anchor = payload.get("anchor_text", "")
        if not anchor:
            continue

        slug = payload.get("slug", payload.get("uid", "?"))

        pos = doc_text.find(anchor)
        if pos == -1:
            errors.append({"slug": slug, "error": f"Anchor not found: {anchor[:60]}"})
            continue

        # Resolve __COMPUTED__ and __OFFSET__ placeholders
        insert_idx = pos + len(anchor) + 1
        requests = []
        for req in payload["requests"]:
            req_str = json.dumps(req)
            req_str = req_str.replace('"__COMPUTED__"', str(insert_idx))
            req_str = req_str.replace('"__OFFSET__+', '"')
            resolved = json.loads(req_str)

            # Adjust offset-based indices
            if "updateTextStyle" in resolved:
                rng = resolved["updateTextStyle"]["range"]
                for key in ("startIndex", "endIndex"):
                    if isinstance(rng[key], str) and rng[key].isdigit():
                        rng[key] = int(rng[key]) + insert_idx

            requests.append(resolved)

        try:
            await client.batch_update(doc_id, requests)
            deployed.append(slug)
        except GoogleClientError as e:
            errors.append({"slug": slug, "error": str(e)})

    return {
        "deployed": len(deployed),
        "errors": len(errors),
        "deployed_slugs": deployed,
        "error_details": errors,
    }


def _load_gdocs_payloads() -> list[dict[str, Any]] | None:
    """Load rendered GDocs payloads from disk, or None if unavailable."""
    gdocs_path = pipeline_config.SITE_DIR / "gdocs_inject.json"
    if not gdocs_path.exists():
        return None
    payloads = json.loads(gdocs_path.read_text(encoding="utf-8"))
    return payloads or None


async def deploy_selected(doc_id: str, uids: list[str]) -> dict[str, Any]:
    """Deploy only selected project UIDs to a Google Doc."""
    payloads = _load_gdocs_payloads()
    if payloads is None:
        return {"error": "No GDocs payloads found. Run render first."}

    uid_set = set(uids)
    filtered = [p for p in payloads if p.get("uid") in uid_set or p.get("slug") in uid_set]
    if not filtered:
        return {"error": f"No matching payloads for the {len(uids)} selected UIDs."}

    return await _deploy_payloads(doc_id, filtered)


async def deploy_to_gdocs(doc_id: str) -> dict[str, Any]:
    """Push all GDocs injection payloads to a Google Doc."""
    payloads = _load_gdocs_payloads()
    if payloads is None:
        return {"error": "No GDocs payloads found. Run render first."}

    return await _deploy_payloads(doc_id, payloads)
