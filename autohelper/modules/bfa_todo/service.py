"""BFA To Do List service — orchestrates pipeline operations."""

from __future__ import annotations

import calendar
import json
import re
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from autohelper.shared.logging import get_logger
from autohelper.shared.paths import data_dir

from .google_client import GoogleDocsClient, GoogleClientError
from .pipeline import config as pipeline_config
from .pipeline.repo import BfaProjectRepo, BfaAliasRepo, seed_from_yaml

logger = get_logger(__name__)

# Source data for seeding
_BFA_TODO_SOURCE = Path("C:/Users/Neal/dev/BFA-todo/data")

# Singleton repos
_project_repo = BfaProjectRepo()
_alias_repo = BfaAliasRepo()


def _ensure_data_dir() -> Path:
    """Ensure output directories exist (site, assets)."""
    d = pipeline_config.DATA_DIR
    d.mkdir(parents=True, exist_ok=True)
    pipeline_config.SITE_DIR.mkdir(parents=True, exist_ok=True)
    pipeline_config.ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    return d


def _ensure_seeded() -> None:
    """Seed SQLite from YAML if the bfa_projects table is empty."""
    if _project_repo.count(include_archived=True) > 0:
        return

    # Try seeding from existing YAML data directory
    _ensure_data_dir()
    pipeline_config.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    # First try: copy from BFA-todo source if YAML dir is empty
    index_path = pipeline_config.DATA_DIR / "index.yaml"
    if not index_path.exists() and _BFA_TODO_SOURCE.exists():
        src_index = _BFA_TODO_SOURCE / "index.yaml"
        if src_index.exists():
            shutil.copy2(str(src_index), str(index_path))
        src_aliases = _BFA_TODO_SOURCE / "aliases.yaml"
        if src_aliases.exists():
            shutil.copy2(str(src_aliases), str(pipeline_config.ALIASES_FILE))
        src_projects = _BFA_TODO_SOURCE / "projects"
        if src_projects.exists():
            for f in src_projects.glob("*.yaml"):
                shutil.copy2(str(f), str(pipeline_config.PROJECTS_DIR / f.name))
        logger.info("Copied YAML seed data from %s", _BFA_TODO_SOURCE)

    # Now seed SQLite from whatever YAML exists
    count = seed_from_yaml()
    if count:
        logger.info("Seeded %d BFA projects into SQLite from YAML", count)


def import_from_html_dir(path: str) -> dict[str, Any]:
    """Force re-import YAML data from a BFA HTML source directory, then seed into SQLite."""
    src = Path(path)
    if not src.exists():
        raise FileNotFoundError(f"Directory not found: {path}")

    _ensure_data_dir()
    pipeline_config.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    # Copy YAML files to local data dir
    src_index = src / "index.yaml"
    if src_index.exists():
        shutil.copy2(str(src_index), str(pipeline_config.DATA_DIR / "index.yaml"))
    src_aliases = src / "aliases.yaml"
    if src_aliases.exists():
        shutil.copy2(str(src_aliases), str(pipeline_config.ALIASES_FILE))
    src_projects = src / "projects"
    count = 0
    if src_projects.exists():
        for f in src_projects.glob("*.yaml"):
            shutil.copy2(str(f), str(pipeline_config.PROJECTS_DIR / f.name))
            count += 1

    # Re-seed SQLite from the updated YAML
    seed_from_yaml()
    logger.info("Imported %d project files from %s", count, path)
    return {"project_count": count, "source": path}


def import_from_html_file(filepath: str) -> dict[str, Any]:
    """Import from a raw Google Docs HTML export through the full pipeline.

    Parses the HTML, extracts gdocs CSS, processes projects with StyleResolver,
    saves to SQLite, and runs a full render.
    """
    src = Path(filepath)
    if not src.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    from .pipeline.importer import import_document
    from .pipeline.processor import process_project
    from .pipeline.style_resolver import StyleResolver
    from .pipeline.renderer import render_all

    _ensure_data_dir()

    # Archive a versioned copy of the source HTML so it's never lost
    from datetime import date
    archive_dir = pipeline_config.DATA_DIR / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().strftime("%Y_%m_%d")
    archive_path = archive_dir / f"{today}_gdocs_source.html"
    shutil.copy2(str(src), str(archive_path))
    # Also keep a stable "current" copy
    shutil.copy2(str(src), str(pipeline_config.DATA_DIR / "current_list.html"))
    logger.info("Archived source HTML: %s", archive_path)

    # Parse HTML → raw project blocks + gdocs CSS
    projects, gdocs_css = import_document(filepath)

    # Process each project (clean, classify, compute runs)
    resolver = StyleResolver(gdocs_css)
    processed = []
    for p in projects:
        processed.append(process_project(p, resolver=resolver))

    # Save to SQLite (transaction-wrapped batch)
    # allow_curated=True: re-import IS the authoritative source of curated content
    _project_repo.upsert_batch(processed, allow_curated=True)

    # Persist gdocs CSS so render_pipeline() and render_one() can reload it
    (pipeline_config.ASSETS_DIR / "gdocs.css").write_text(gdocs_css, encoding="utf-8")

    # Run full render to produce canonical.css, index_pasteable.html, etc.
    render_all(processed, gdocs_css)

    project_count = sum(1 for p in processed if p.get("type") == "project")
    logger.info("Imported %d projects from HTML file %s", project_count, filepath)
    return {"project_count": project_count, "source": filepath}


def get_status() -> dict[str, Any]:
    """Return pipeline status summary."""
    _ensure_seeded()

    project_count = _project_repo.count()

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


def _collect_preambles() -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Load preamble blocks, merging extra preamble snippets into preamble-lists."""
    preamble_items = _project_repo.get_by_type("preamble", "preamble-lists")
    overview = None
    proposals = None
    extras: list[dict[str, Any]] = []

    for p in preamble_items:
        ptype = p.get("type")
        if ptype == "preamble":
            if overview is None:
                overview = p
            else:
                extras.append(p)
        elif ptype == "preamble-lists":
            proposals = p

    # Fold extra preamble snippets into the proposals block
    if proposals and extras:
        content = proposals.get("sections", {}).get("content", {})
        html = content.get("html", "")
        text = content.get("text", "")
        for ex in extras:
            ex_content = ex.get("sections", {}).get("content", {})
            ex_html = ex_content.get("html", "")
            ex_text = ex_content.get("text", "")
            if ex_html.strip():
                html = html.rstrip() + "\n" + ex_html
                text = text.rstrip() + "\n" + ex_text
        proposals.setdefault("sections", {}).setdefault("content", {})
        proposals["sections"]["content"]["html"] = html
        proposals["sections"]["content"]["text"] = text

    return overview, proposals


def list_preambles() -> list[dict[str, Any]]:
    """Return summary list of preamble blocks (2 items: overview + proposals)."""
    _ensure_seeded()

    overview, proposals = _collect_preambles()
    result = []
    if overview:
        result.append({
            "uid": overview["uid"],
            "slug": overview.get("slug", ""),
            "type": "preamble",
            "title": "Projects Overview",
        })
    if proposals:
        result.append({
            "uid": proposals["uid"],
            "slug": proposals.get("slug", ""),
            "type": "preamble-lists",
            "title": "Proposals & Programs",
        })
    return result


def get_preamble_html(uid: str) -> str | None:
    """Return fully-inlined HTML for a single preamble block."""
    overview, proposals = _collect_preambles()
    target = None
    if overview and overview["uid"] == uid:
        target = overview
    elif proposals and proposals["uid"] == uid:
        target = proposals

    if not target:
        return None

    from .pipeline.renderer import render_one
    return render_one(target)


def list_projects() -> list[dict[str, Any]]:
    """Return summary list of all projects with validation diagnostics."""
    from .pipeline.processor import derive_metadata
    from .pipeline.validator import validate_all

    _ensure_seeded()

    all_projects = _project_repo.get_all()
    project_list = [p for p in all_projects if p.get("type") == "project"]

    # Run batch validation (includes cross-project checks like duplicates)
    all_diags = validate_all(project_list)

    summaries = []
    for p in project_list:
        meta = derive_metadata(p)
        uid = p["uid"]
        diags = all_diags.get(uid, [])
        errors = [d for d in diags if d.level == "error"]
        warnings = [d for d in diags if d.level == "warning"]
        summaries.append({
            "uid": uid,
            "slug": p.get("slug", ""),
            "client": p.get("fields", {}).get("client", "TBC"),
            "project_name": p.get("fields", {}).get("project_name", "TBC"),
            "city": p.get("fields", {}).get("city", "TBC"),
            "phase": meta["bfa_phase_canonical"],
            "owner_team": p.get("fields", {}).get("owner_team", "BFA"),
            "status": p.get("status", "active"),
            "validation": {
                "error_count": len(errors),
                "warning_count": len(warnings),
                "items": [d.to_dict() for d in diags],
            },
        })
    return summaries


def get_project(uid: str) -> dict[str, Any] | None:
    """Return a single project's full data with inline_html, derived metadata,
    and section_meta for the composition view."""
    from .pipeline.processor import derive_metadata, get_section_meta

    project = _project_repo.get(uid)
    if not project:
        return None

    _enrich_inline_html(project)
    project["derived"] = derive_metadata(project)
    project["section_meta"] = get_section_meta(project.get("sections", {}))

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
    """Compute inline_html for sections that have raw html but no inline_html."""
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
    """Return fully-inlined HTML for a single project via the render pipeline."""
    project = _project_repo.get(uid)
    if not project or project.get("type") != "project":
        return None

    from .pipeline.renderer import render_one
    return render_one(project)


def update_project(uid: str, changes: dict[str, Any]) -> dict[str, Any] | None:
    """Update editable fields on a project and persist to SQLite."""
    project = _project_repo.get(uid)
    if not project:
        return None

    fields = project.get("fields", {})
    sections = project.get("sections", {})

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
    _project_repo.upsert(project)

    return {"uid": uid, "updated": list(changes.keys())}


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
    """Update section HTML from contenteditable edits and persist to SQLite."""
    project = _project_repo.get(uid)
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
    _project_repo.upsert(project)

    return {"uid": uid, "updated_sections": list(section_htmls.keys())}


def update_project_section(
    uid: str,
    section_name: str,
    html: str,
) -> dict[str, Any] | None:
    """Update a single section's HTML and persist to SQLite.

    Allows curated content edits — this is always a deliberate user action
    via the composition view (preamble or project section edit).
    """
    from .pipeline.processor import derive_metadata, get_section_meta

    project = _project_repo.get(uid)
    if not project:
        return None

    sections = project.get("sections", {})
    if section_name not in sections:
        sections[section_name] = {}

    sections[section_name]["html"] = html
    sections[section_name]["text"] = _html_to_text(html)
    project["sections"] = sections
    _project_repo.upsert(project, allow_curated=True)

    _enrich_inline_html(project)
    project["derived"] = derive_metadata(project)
    project["section_meta"] = get_section_meta(sections)

    return project


def update_project_phase(uid: str, phase: str) -> dict[str, Any] | None:
    """Update a project's phase via dropdown selection."""
    from .pipeline.processor import derive_metadata, get_section_meta

    project = _project_repo.get(uid)
    if not project:
        return None

    sections = project.get("sections", {})
    if "bfa_phase" not in sections:
        sections["bfa_phase"] = {}

    sections["bfa_phase"]["text"] = phase
    sections["bfa_phase"]["html"] = f'<p><strong>Project Status:</strong> {phase}</p>'
    project["sections"] = sections
    project["bfa_phase_canonical"] = phase
    _project_repo.upsert(project)

    _enrich_inline_html(project)
    project["derived"] = derive_metadata(project)
    project["section_meta"] = get_section_meta(sections)

    return project


def suggest_preamble_updates() -> list[dict[str, Any]]:
    """Compare project state against curated preamble-lists and return suggestions.

    Does NOT modify the DB.  Returns a list of suggestion dicts:
      {"category": str, "project": str, "uid": str, "suggestion": str}
    """
    from collections import defaultdict

    entries = _project_repo.get_all(include_archived=False)
    projects = [e for e in entries if e.get("type") == "project"]

    if not projects:
        return []

    # Load current preamble-lists text to check what's already mentioned
    preamble_lists = _project_repo.get("e2adb95f-4ae7-5d77-916f-bb6b714e045a")
    existing_text = ""
    if preamble_lists:
        existing_text = (
            preamble_lists.get("sections", {}).get("content", {}).get("text", "")
        ).lower()

    PHASE_TO_CATEGORY = {
        "1. Project Initiation": "Proposals (New Projects)",
        "2. PPAP": "Art Plans to be drafted",
        "3. DPAP": "Art Plans to be drafted",
        "4.1. Artist Selection SP#1": "Longlists",
        "4.2. Artist Selection SP#2": "Artist Contracts",
        "5. Artist Contract": "Artist Contracts",
        "9. 100% Fabrication/Install": "Final Documents and Installation",
        "10. Final Documents": "Final Documents and Installation",
    }

    suggestions: list[dict[str, Any]] = []

    for p in projects:
        phase = p.get("bfa_phase_canonical") or "TBC"
        status = p.get("status", "active")
        fields = p.get("fields", {})
        name = fields.get("project_name", "") or fields.get("client", "")

        if not name:
            continue

        # Determine expected category
        if status == "on_hold":
            expected_cat = "ON HOLD"
        elif phase in ("", "TBC"):
            expected_cat = "Proposals (New Projects)"
        else:
            expected_cat = PHASE_TO_CATEGORY.get(phase)

        if not expected_cat:
            # phases 6-8 are active work — no preamble-lists entry expected
            continue

        # Check if project name already appears in the curated text
        if name.lower() in existing_text:
            continue

        suggestions.append({
            "category": expected_cat,
            "project": name,
            "uid": p["uid"],
            "phase": phase,
            "suggestion": f"{name} is in {phase} — consider adding to {expected_cat}",
        })

    if suggestions:
        logger.info(
            "Preamble-lists suggestions: %d projects not yet listed",
            len(suggestions),
        )

    return suggestions


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """Return the nth occurrence of weekday in the given month.

    weekday: 0=Mon, 1=Tue, ..., 6=Sun.  n: 1-based (1=first, 2=second).
    """
    first_day = date(year, month, 1)
    # Days until the first occurrence of weekday in this month
    offset = (weekday - first_day.weekday()) % 7
    target = first_day + timedelta(days=offset + 7 * (n - 1))
    return target


def _next_n_meetings(weekday: int, nth: int, count: int = 2, ref: date | None = None) -> list[date]:
    """Return the next `count` meeting dates for an nth-weekday-of-month rule."""
    today = ref or date.today()
    results: list[date] = []
    year, month = today.year, today.month

    for _ in range(count + 12):  # safety bound
        d = _nth_weekday(year, month, weekday, nth)
        if d >= today:
            results.append(d)
            if len(results) == count:
                break
        # Advance to next month
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1

    return results


def _format_meeting_date(d: date) -> str:
    """Format as 'Mon DD, YYYY' e.g. 'Apr 8, 2026'."""
    return f"{d.strftime('%b')} {d.day}, {d.year}"


def refresh_dynamic_preamble_dates() -> int:
    """Update auto-computed meeting dates in the main preamble.

    Rules:
      Richmond (RPAAC): 2nd Tuesday of each month, 4:30 PM
      North Van: 2nd Thursday of each month, 6–8 PM

    Updates the corresponding lines in the preamble content section.
    Returns the number of lines updated.
    """
    preambles = _project_repo.get_by_type("preamble")
    if not preambles:
        return 0

    # Find the main preamble (the one with PAC meeting content)
    main = None
    for p in preambles:
        text = p.get("sections", {}).get("content", {}).get("text", "")
        if "Richmond:" in text or "PUBLIC ART COMMITTEE" in text:
            main = p
            break
    if not main:
        return 0

    text = main["sections"]["content"]["text"]
    lines = text.split("\n")
    updated = 0
    today = date.today()

    for i, line in enumerate(lines):
        # Title line: "Ballard Fine Art - To Do List <date>"
        # Date is always the next Monday (generated Fridays, delivered Mondays)
        if line.startswith("Ballard Fine Art - To Do List"):
            days_until_monday = (7 - today.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7  # if today is Monday, use next Monday
            monday = today + timedelta(days=days_until_monday)
            lines[i] = f"Ballard Fine Art - To Do List {monday.strftime('%B')} {monday.day}, {monday.year}"
            updated += 1

        # Richmond: 2nd Tuesday
        elif line.startswith("Richmond:") and "biliana" in line.lower():
            dates = _next_n_meetings(weekday=calendar.TUESDAY, nth=2, count=2, ref=today)
            date_str = ", ".join(_format_meeting_date(d) for d in dates)
            lines[i] = (
                f"Richmond: {date_str} "
                f"*confirm with Biliana 2 weeks prior to the target date to present."
            )
            updated += 1

        # North Van: 2nd Thursday
        elif line.startswith("North Van:") and "lori" in line.lower():
            dates = _next_n_meetings(weekday=calendar.THURSDAY, nth=2, count=2, ref=today)
            date_str = ", ".join(_format_meeting_date(d) for d in dates)
            lines[i] = (
                f"North Van: 2nd Thurs (6pm-8pm) Upcoming dates: {date_str} "
                f"*confirm with Lori Phillips 2 weeks prior the target date to present. "
                f"DNV meetings are held at Delbrook Rec Centre"
            )
            updated += 1

    if updated:
        new_text = "\n".join(lines)
        import html as html_mod
        new_html = "\n".join(
            f"<p>{html_mod.escape(ln)}</p>" for ln in lines if ln.strip()
        )
        _project_repo.update_section(
            main["uid"], "content", new_text, new_html, allow_curated=True,
        )
        logger.info("Refreshed %d dynamic preamble date lines", updated)

    return updated


def render_pipeline() -> dict[str, Any]:
    """Run the render pipeline: load from SQLite -> render HTML + JSON + GDocs payloads."""
    from .pipeline.renderer import render_all

    _ensure_seeded()

    # Refresh dynamic dates in preamble before rendering
    try:
        refresh_dynamic_preamble_dates()
    except Exception as e:
        logger.warning("Dynamic preamble date refresh failed: %s", e)

    # Surface suggestions for preamble-lists (read-only — curated content is never overwritten)
    try:
        suggestions = suggest_preamble_updates()
        if suggestions:
            logger.info(
                "Preamble-lists has %d suggested additions (not applied — content is curated)",
                len(suggestions),
            )
    except Exception as e:
        logger.warning("Preamble-lists suggestion check failed: %s", e)
        suggestions = []

    projects = _project_repo.get_all(include_archived=False)
    if not projects:
        return {"error": "No projects found", "outputs": {}}

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
        "preamble_suggestions": suggestions,
    }


def import_excel(filepath: str) -> dict[str, Any]:
    """Import a Monday.com Excel export and return match report."""
    from .pipeline.excel_importer import import_excel as _import_excel
    from .pipeline.matcher import match
    from .pipeline.differ import diff_matched, diff_rollups

    _ensure_seeded()

    excel_rows = _import_excel(filepath)

    projects = _project_repo.get_all(include_archived=False)
    aliases = _alias_repo.get()

    match_report = match(excel_rows, projects, aliases)

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

        insert_idx = pos + len(anchor) + 1
        requests = []
        for req in payload["requests"]:
            req_str = json.dumps(req)
            req_str = req_str.replace('"__COMPUTED__"', str(insert_idx))
            req_str = req_str.replace('"__OFFSET__+', '"')
            resolved = json.loads(req_str)

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
    """Push full To Do list to a Google Doc.

    For blank/new docs: inserts all content sequentially (preambles + projects).
    For existing docs with anchors: updates in place.
    """
    # First try: check if doc has content (anchor-based update)
    payloads = _load_gdocs_payloads()
    if payloads is None:
        return {"error": "No GDocs payloads found. Run render first."}

    client = GoogleDocsClient()
    try:
        doc = await client.get_document(doc_id)
    except GoogleClientError as e:
        return {"error": str(e)}

    # Check if doc has content
    doc_text = ""
    for element in doc.get("body", {}).get("content", []):
        paragraph = element.get("paragraph")
        if paragraph:
            for el in paragraph.get("elements", []):
                text_run = el.get("textRun")
                if text_run:
                    doc_text += text_run.get("content", "")

    if doc_text.strip():
        # Existing doc with content — use anchor-based update
        return await _deploy_payloads(doc_id, payloads)

    # Blank doc — insert everything sequentially
    return await _deploy_full(doc_id, payloads)


async def _deploy_full(
    doc_id: str, payloads: list[dict[str, Any]]
) -> dict[str, Any]:
    """Deploy full content to a blank Google Doc with styling.

    Uses the pre-computed payloads (which now include preambles) with their
    insertText + updateTextStyle requests. Resolves all relative offsets
    (__OFFSET__+N) to absolute document indices.
    """
    client = GoogleDocsClient()

    # Build full text from all payloads in order, tracking absolute positions
    full_text = ""
    all_style_requests: list[dict[str, Any]] = []

    for payload in payloads:
        anchor = payload.get("anchor_text", "")

        # Insert anchor (header) line for projects
        if anchor:
            anchor_start = len(full_text)
            full_text += anchor + "\n"
            anchor_end = len(full_text) - 1
            all_style_requests.append({
                "updateTextStyle": {
                    "range": {"startIndex": anchor_start + 1, "endIndex": anchor_end + 1},
                    "textStyle": {"bold": True, "underline": True},
                    "fields": "bold,underline",
                }
            })

        # Insert body text + resolve style offsets
        for req in payload.get("requests", []):
            if "insertText" in req:
                body_text = req["insertText"]["text"]
                insert_offset = len(full_text)
                full_text += body_text

                # Resolve all style requests from this payload
                for style_req in payload["requests"]:
                    if "updateTextStyle" not in style_req:
                        continue
                    uts = style_req["updateTextStyle"]
                    rng = uts["range"]
                    start_str = str(rng["startIndex"])
                    end_str = str(rng["endIndex"])
                    if "__OFFSET__+" in start_str:
                        rel_start = int(start_str.split("+")[1])
                        rel_end = int(end_str.split("+")[1])
                        abs_start = insert_offset + rel_start + 1  # +1 for doc index
                        abs_end = insert_offset + rel_end + 1
                        if abs_start < abs_end:
                            all_style_requests.append({
                                "updateTextStyle": {
                                    "range": {"startIndex": abs_start, "endIndex": abs_end},
                                    "textStyle": uts["textStyle"],
                                    "fields": uts["fields"],
                                }
                            })
                break  # only one insertText per payload

        full_text += "\n"

    if not full_text.strip():
        return {"error": "No content to deploy"}

    # Build request list: insert text first, then all styling
    requests: list[dict[str, Any]] = [
        {"insertText": {"location": {"index": 1}, "text": full_text}}
    ]
    requests.extend(all_style_requests)

    logger.info("Full deploy: %d chars, %d style requests", len(full_text), len(all_style_requests))

    # Batch in chunks to avoid quota issues
    CHUNK = 500
    deployed = 0
    errors: list[str] = []
    for i in range(0, len(requests), CHUNK):
        chunk = requests[i:i + CHUNK]
        try:
            await client.batch_update(doc_id, chunk)
            deployed += len(chunk)
        except GoogleClientError as e:
            if "429" in str(e):
                import asyncio as aio
                await aio.sleep(65)
                try:
                    await client.batch_update(doc_id, chunk)
                    deployed += len(chunk)
                except GoogleClientError as e2:
                    errors.append(str(e2)[:100])
            else:
                errors.append(str(e)[:100])

    return {
        "deployed": len(payloads),
        "requests_sent": deployed,
        "errors": len(errors),
        "error_details": errors,
        "method": "full_insert_styled",
        "total_chars": len(full_text),
    }


# ---------------------------------------------------------------------------
# .docx round-trip: import → diff → apply → push to ClickUp
# ---------------------------------------------------------------------------

def import_from_docx(docx_path: str) -> dict[str, Any]:
    """Parse a .docx file and diff against DB.

    Returns deltas for UI review.  Does NOT modify the DB.
    """
    from .adapter import docx_to_projects, diff_projects

    _ensure_seeded()

    parsed = docx_to_projects(docx_path)
    db_entries = _project_repo.get_all(include_archived=False)
    deltas = diff_projects(parsed, db_entries)

    return {
        "parsed_count": len(parsed),
        "db_count": len([e for e in db_entries if e.get("type") == "project"]),
        "delta_count": len(deltas),
        "deltas": [
            {
                "uid": d.uid,
                "header": d.header_text[:80],
                "category": d.category,
                "name": d.name,
                "old": d.old[:200],
                "new": d.new[:200],
            }
            for d in deltas
        ],
    }


def apply_docx_deltas(deltas: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply confirmed deltas from .docx import to the DB.

    Each delta dict: {uid, category, name, new}
    - category "field": update fields[name]
    - category "section": update section text + regenerate HTML
    """
    from .pipeline.processor import _text_to_html

    applied = 0
    errors: list[str] = []

    for delta in deltas:
        uid = delta["uid"]
        entry = _project_repo.get(uid)
        if not entry:
            errors.append(f"Entry {uid} not found")
            continue

        try:
            if delta["category"] == "field":
                fields = entry.get("fields", {})
                fields[delta["name"]] = delta["new"]
                entry["fields"] = fields
                # Rebuild header from updated fields
                header_text = entry.get("header", {}).get("text", "")
                if delta["name"] in ("owner_team", "client", "project_name", "city",
                                      "art_budget", "total_budget", "install_date"):
                    from .clickup_sync import _build_header
                    f = entry["fields"]
                    entry["header"] = _build_header(
                        f.get("owner_team", "BFA"), f.get("client", ""),
                        f.get("project_name", ""), f.get("city", "TBC"),
                        f.get("art_budget", "$TBC"), f.get("total_budget", "$TBC"),
                        f.get("install_date", "TBC"),
                    )

            elif delta["category"] == "section":
                sections = entry.get("sections", {})
                sec = sections.get(delta["name"], {})
                sec["text"] = delta["new"]
                sec["html"] = "\n".join(
                    f"<p>{_text_to_html(line)}</p>"
                    for line in delta["new"].split("\n")
                    if line.strip()
                )
                sections[delta["name"]] = sec
                entry["sections"] = sections

            _project_repo.upsert(entry)
            applied += 1

        except Exception as e:
            errors.append(f"{uid}/{delta['name']}: {e}")
            logger.warning("Delta apply error: %s", e)

    return {"applied": applied, "errors": errors}


async def push_changes_to_clickup(uids: list[str]) -> dict[str, Any]:
    """Push BFA entry changes to ClickUp for provisioned projects.

    For each uid, finds the matching ProjectRecord and updates the
    ClickUp task with current BFA fields and sections.
    """
    from .adapter import project_to_clickup_updates
    from autohelper.modules.clickup.client import ClickUpClient
    from autohelper.modules.projects.store import get_project_store

    store = get_project_store()
    all_project_records = store.list_all()
    records_by_id = {pr.id: pr for pr in all_project_records}

    updated = 0
    errors: list[str] = []

    for uid in uids:
        entry = _project_repo.get(uid)
        if not entry:
            errors.append(f"BFA entry {uid} not found")
            continue

        fields = entry.get("fields", {})
        proj_name = fields.get("project_name", "")
        client = fields.get("client", "")

        # Primary: use stored project_record_id
        record = None
        rec_id = entry.get("project_record_id")
        if rec_id:
            record = records_by_id.get(rec_id)

        # Fallback: name-based matching (legacy entries)
        if not record:
            for pr in all_project_records:
                if (proj_name.lower() in pr.project_name.lower()
                        or pr.project_name.lower() in proj_name.lower()):
                    record = pr
                    break
                if client and client.lower() in (pr.developer_name or "").lower():
                    record = pr
                    break
            # Backfill the identity link
            if record and not rec_id:
                entry["project_record_id"] = record.id
                _project_repo.upsert(entry)

        if not record or not record.clickup_list_id:
            errors.append(f"No ClickUp project for {client} - {proj_name}")
            continue

        try:
            update = project_to_clickup_updates(entry, record)

            cu = ClickUpClient()

            # Get tasks in the list to find the root/summary task
            tasks_resp = await cu._request("GET", f"/list/{record.clickup_list_id}/task",
                                           params={"subtasks": "false", "page": "0"})
            tasks = tasks_resp.get("tasks", [])

            if not tasks:
                errors.append(f"No tasks in ClickUp list for {proj_name}")
                continue

            # Update the first task (summary task) with description
            task_id = tasks[0]["id"]
            await cu._request("PUT", f"/task/{task_id}", json={
                "name": update["task_name"],
                "description": update["description"],
            })

            # Post comment if there are new notes
            if update.get("comment"):
                await cu._request("POST", f"/task/{task_id}/comment", json={
                    "comment_text": update["comment"],
                })

            updated += 1
            logger.info("Pushed to ClickUp: %s (task %s)", proj_name, task_id)

        except Exception as e:
            errors.append(f"{proj_name}: {e}")
            logger.warning("ClickUp push error for %s: %s", proj_name, e)

    return {"updated": updated, "errors": errors}
