"""
ClickUp -> BFA To Do List sync.

Pulls provisioned projects from the Projects module, fetches live task status
from ClickUp via stage_monitor, and creates/updates BFA To Do entries.

Generated entries match the original .docx format:
  (TEAM) Client: Project, City (Artwork: $X) (Total: $Y) Install: DATE
  Contact: ...
  Owner: ...
  Architect: ...  Landscape: ...
  PPAP: ...  DPAP: ...  EOI: ...
  SP#1: ...  AO: ...  SP#2: ...
  Selection Panel: ...
  Shortlisted Artists: TBD
  Selected Artist: TBD
  Artwork Title: TBD
  Project Status: ...
  Next Steps: ...

Client short names are resolved via client_aliases in bfa_aliases.  New
developer names get a best-effort parse that PMs refine in the alias table.

Workflow:
  PMs work in ClickUp daily -> Monday morning this runs ->
  To Do list regenerated -> deployed to Google Docs for owner.
"""

from __future__ import annotations

import html as html_mod
import logging
import re
from typing import Any

from autohelper.shared.ids import generate_id

logger = logging.getLogger(__name__)

# Developer name suffixes to strip when building best-effort short names
_DEV_SUFFIXES = {
    "investments", "properties", "development", "developments", "developer",
    "developers", "corp", "corporation", "group", "homes", "inc", "ltd",
    "llc", "lp", "realty", "real estate", "construction", "holdings",
}


# ---------------------------------------------------------------------------
# Client alias resolution
# ---------------------------------------------------------------------------

def _load_client_aliases() -> dict[str, str]:
    """Load client_aliases from the bfa_aliases table."""
    from .pipeline.repo import BfaAliasRepo
    aliases = BfaAliasRepo().get()
    return aliases.get("client_aliases", {})


def _save_client_aliases(client_aliases: dict[str, str]) -> None:
    """Persist updated client_aliases back to the bfa_aliases table."""
    from .pipeline.repo import BfaAliasRepo
    repo = BfaAliasRepo()
    aliases = repo.get()
    aliases["client_aliases"] = client_aliases
    repo.save(aliases)


def _resolve_client_short_name(
    developer_name: str | None,
    project_name: str,
    client_aliases: dict[str, str],
) -> tuple[str, bool]:
    """Resolve short client display name.

    Checks client_aliases first.  Falls back to best-effort parsing:
      "Starlight - Lougheed Village P1" -> "Starlight"
      "Starlight Investments" -> "Starlight"

    Returns (short_name, is_new) where is_new means the alias table
    should be updated with this best-effort name.
    """
    # 1. Exact match in alias table (keyed by full developer_name)
    if developer_name and developer_name in client_aliases:
        return client_aliases[developer_name], False

    # 2. Best-effort: parse from "Client - Project" naming convention
    parts = project_name.split(" - ", 1)
    if len(parts) >= 2:
        short = parts[0].strip()
    elif developer_name:
        # Strip common corporate suffixes
        words = developer_name.split()
        kept = [w for w in words if w.lower() not in _DEV_SUFFIXES]
        short = " ".join(kept) if kept else words[0]
    else:
        short = project_name

    return short, True


# ---------------------------------------------------------------------------
# Budget formatting
# ---------------------------------------------------------------------------

def _fmt_budget(amount: float | None) -> str:
    """Format a budget amount for the header.  Zero/None -> '$TBC'."""
    if not amount:
        return "$TBC"
    if amount >= 1_000:
        return f"${amount:,.0f}"
    return f"${amount:,.2f}"


# ---------------------------------------------------------------------------
# Section builders — produce (text, html) matching original .docx format
# ---------------------------------------------------------------------------

def _esc(s: str) -> str:
    return html_mod.escape(s)


def _build_header(
    team: str,
    client: str,
    project_short: str,
    city: str,
    art_budget: str,
    total_budget: str,
    install: str,
) -> dict[str, str]:
    """Build header text + html matching: (TEAM) Client: Project, City (Artwork: $X) (Total: $Y) Install: DATE"""
    text = f"({team}) {client}: {project_short}, {city} (Artwork: {art_budget}) (Total: {total_budget}) Install: {install}"
    html = (
        f'<h3><span style="font-weight:700;text-decoration:underline;font-size:11pt">'
        f'{_esc(text)}'
        f'</span></h3>'
    )
    return {"text": text, "html": html}


def _build_contacts_section(developer_name: str | None) -> dict[str, str]:
    """Contacts section with full field layout, TBC placeholders.

    Uses <strong> tags for bold labels (detected by style_resolver via
    _TAG_STYLES → "bold" → <span style="font-weight:700">).

    Column alignment uses non-breaking spaces (\xa0) not tabs — tabs get
    collapsed by walk_html_for_runs._collapse_ws.  The original GDocs entries
    use \xa0 for the same reason.
    """
    owner = developer_name or "TBC"
    # \xa0 padding for column alignment (matches original GDocs pattern)
    _pad = "\xa0" * 20
    text_lines = [
        "Contact: TBC",
        f"Owner: {owner}",
        f"Architect: TBC{_pad}Landscape: TBC",
        f"PPAP: TBC{_pad}DPAP: TBC{_pad}EOI: TBC",
        f"SP#1: TBC{_pad}AO: TBC{_pad}SP#2: TBC",
        "Selection Panel: TBC",
        "Community Advisory: TBC",
    ]
    html_lines = [
        '<p><strong>Contact:</strong> TBC</p>',
        f'<p><strong>Owner:</strong> {_esc(owner)}</p>',
        f'<p><strong>Architect:</strong> TBC{_pad}<strong>Landscape:</strong> TBC</p>',
        f'<p><strong>PPAP:</strong> TBC{_pad}<strong>DPAP:</strong> TBC{_pad}<strong>EOI:</strong> TBC</p>',
        f'<p><strong>SP#1:</strong> TBC{_pad}<strong>AO:</strong> TBC{_pad}<strong>SP#2:</strong> TBC</p>',
        '<p><strong>Selection Panel:</strong> TBC</p>',
        '<p><strong>Community Advisory:</strong> TBC</p>',
    ]
    return {"text": "\n".join(text_lines), "html": "\n".join(html_lines)}


def _build_artists_section() -> dict[str, str]:
    text = "Shortlisted Artists: TBD\nSelected Artist: TBD"
    html = (
        '<p><strong>Shortlisted Artists:</strong> TBD</p>\n'
        '<p><strong>Selected Artist:</strong> TBD</p>'
    )
    return {"text": text, "html": html}


def _build_artwork_title_section() -> dict[str, str]:
    return {
        "text": "Artwork Title: TBD",
        "html": '<p><strong>Artwork Title:</strong> TBD</p>',
    }


def _build_phase_section(phase_text: str) -> dict[str, str]:
    return {
        "text": f"Project Status: {phase_text}",
        "html": f'<p><strong>Project Status:</strong> {_esc(phase_text)}</p>',
    }


def _build_next_steps_section(lines: list[str]) -> dict[str, str]:
    """Next Steps as 'Next Steps: summary' — matching original bold-label format."""
    if not lines:
        return {
            "text": "Next Steps: TBC",
            "html": '<p><strong>Next Steps:</strong> TBC</p>',
        }
    summary = ", ".join(lines)
    return {
        "text": f"Next Steps: {summary}",
        "html": f'<p><strong>Next Steps:</strong> {_esc(summary)}</p>',
    }


# ---------------------------------------------------------------------------
# Entry builder
# ---------------------------------------------------------------------------

def _project_to_todo_entry(
    project: Any,
    client_aliases: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Convert a Projects module ProjectRecord to a BFA To Do entry dict.

    Produces a complete entry matching the original .docx format with all
    standard sections.  Uses client_aliases for the short developer name.
    """
    if client_aliases is None:
        client_aliases = _load_client_aliases()

    # -- Resolve names --
    client_short, _is_new = _resolve_client_short_name(
        project.developer_name, project.project_name, client_aliases,
    )

    # Parse project short name: "Starlight - Lougheed Village P1" -> "Lougheed Village P1"
    parts = project.project_name.split(" - ", 1)
    project_short = parts[1].strip() if len(parts) >= 2 else project.project_name

    # -- City --
    city = project.city_name
    for prefix in ("City of ", "District of "):
        if city.startswith(prefix):
            city = city[len(prefix):]

    # -- Budget --
    art_budget = _fmt_budget(project.budget.art_contribution if project.budget else None)
    total_budget = _fmt_budget(project.budget.total if project.budget else None)

    # -- Install date --
    install = project.install_date or "TBC"

    # -- Team code (PM team — default BFA, refined by PM) --
    team = "BFA"

    # -- Build header --
    header = _build_header(team, client_short, project_short, city, art_budget, total_budget, install)

    # -- Build sections in canonical display order --
    initial_phase = "1. Project Initiation"
    sections = {
        "contacts": _build_contacts_section(project.developer_name),
        "artists": _build_artists_section(),
        "artwork_title": _build_artwork_title_section(),
        "bfa_phase": _build_phase_section(initial_phase),
        "next_steps": _build_next_steps_section([]),
    }

    return {
        "uid": generate_id("bfa"),
        "slug": project.project_name.lower().replace(" ", "-").replace(".", ""),
        "type": "project",
        "status": "active",
        "source": "clickup",
        "fields": {
            "client": client_short,
            "project_name": project.project_name,
            "city": city,
            "art_budget": art_budget,
            "total_budget": total_budget,
            "install_date": install,
            "artists_text": "TBD",
            "contacts_text": "TBC",
            "owner_team": team,
        },
        "header": header,
        "sections": sections,
        "bfa_phase_canonical": initial_phase,
        "bfa_phase_display": initial_phase,
    }


# ---------------------------------------------------------------------------
# Phase update (for existing entries on re-sync)
# ---------------------------------------------------------------------------

def _update_entry_phase(entry: dict[str, Any], project: Any) -> None:
    """Update an existing entry from the project record.

    Preserves PM-managed content (sections, notes).  Only fills in fields
    that are currently TBC/empty from ProjectRecord data.  Marks the entry
    as clickup-sourced.  Does NOT overwrite a richer original header — only
    rebuilds the header if the existing one is a bare ClickUp-generated one.
    """
    fields = entry.get("fields", {})

    # Mark as clickup-linked (preserves original content but tracks provenance)
    if entry.get("source") is None:
        entry["source"] = "clickup"

    # Fill in TBC fields from ProjectRecord — don't overwrite existing values
    if project.budget:
        art = _fmt_budget(project.budget.art_contribution)
        total = _fmt_budget(project.budget.total)
        if art != "$TBC" and fields.get("art_budget") in ("$TBC", "", None):
            fields["art_budget"] = art
        if total != "$TBC" and fields.get("total_budget") in ("$TBC", "", None):
            fields["total_budget"] = total

    if project.install_date and fields.get("install_date") in ("TBC", "", None):
        fields["install_date"] = project.install_date

    city = project.city_name
    for prefix in ("City of ", "District of "):
        if city.startswith(prefix):
            city = city[len(prefix):]
    if fields.get("city") in ("TBC", "", None):
        fields["city"] = city

    entry["fields"] = fields

    # Only rebuild header if the existing one is a bare ClickUp-generated header
    # (no budget/install info).  Original entries with rich headers are preserved.
    header_text = entry.get("header", {}).get("text", "")
    is_bare_header = (
        "Artwork" not in header_text
        and "Total" not in header_text
        and "Install" not in header_text
    )
    if is_bare_header:
        client_aliases = _load_client_aliases()
        client_short, _ = _resolve_client_short_name(
            project.developer_name, project.project_name, client_aliases,
        )
        parts = project.project_name.split(" - ", 1)
        project_short = parts[1].strip() if len(parts) >= 2 else project.project_name

        entry["header"] = _build_header(
            fields.get("owner_team", "BFA"),
            client_short,
            project_short,
            fields.get("city", "TBC"),
            fields.get("art_budget", "$TBC"),
            fields.get("total_budget", "$TBC"),
            fields.get("install_date", "TBC"),
        )

    # Ensure sections exist (fill TBC placeholders for any missing ones,
    # but never overwrite existing PM-managed content)
    sections = entry.get("sections", {})
    if "contacts" not in sections:
        sections["contacts"] = _build_contacts_section(project.developer_name)
    if "artists" not in sections:
        sections["artists"] = _build_artists_section()
    if "artwork_title" not in sections:
        sections["artwork_title"] = _build_artwork_title_section()
    if "bfa_phase" not in sections:
        sections["bfa_phase"] = _build_phase_section("TBC")
    if "next_steps" not in sections:
        sections["next_steps"] = _build_next_steps_section([])
    entry["sections"] = sections


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def _find_existing_entry(
    repo: Any, project_name: str, developer_name: str | None
) -> dict[str, Any] | None:
    """Find an existing BFA To Do entry matching this project."""
    all_entries = repo.get_all()
    name_lower = project_name.lower()
    dev_lower = (developer_name or "").lower()

    for entry in all_entries:
        if entry.get("type") != "project":
            continue
        fields = entry.get("fields", {})
        entry_name = fields.get("project_name", "").lower()
        entry_client = fields.get("client", "").lower()

        if name_lower in entry_name or entry_name in name_lower:
            return entry
        if dev_lower and dev_lower in entry_client:
            return entry

    return None


# ---------------------------------------------------------------------------
# Public sync functions
# ---------------------------------------------------------------------------

def sync_from_clickup() -> dict[str, Any]:
    """Pull all provisioned projects and sync into BFA To Do entries.

    For each provisioned project:
    - If no To Do entry exists, create one with full original-format fields
    - If entry exists, refresh header fields (budget, install, city)
    - Sections (contacts, artists, next_steps) are PM-managed, not overwritten
    - New developer names are auto-added to client_aliases for PM refinement

    Returns sync summary.
    """
    from autohelper.modules.projects.service import list_projects
    from autohelper.modules.projects.types import ProjectStatus
    from .pipeline.repo import BfaProjectRepo

    repo = BfaProjectRepo()
    all_projects = list_projects()
    provisioned = [p for p in all_projects if p.status in (ProjectStatus.PROVISIONED, ProjectStatus.ACTIVE)]

    # Load aliases once for the whole sync
    client_aliases = _load_client_aliases()
    aliases_dirty = False

    created = 0
    updated = 0
    errors: list[str] = []

    for project in provisioned:
        try:
            existing = _find_existing_entry(repo, project.project_name, project.developer_name)

            if existing:
                _update_entry_phase(existing, project)
                repo.upsert(existing)
                updated += 1
            else:
                # Resolve alias (may create new best-effort entry)
                short, is_new = _resolve_client_short_name(
                    project.developer_name, project.project_name, client_aliases,
                )
                if is_new and project.developer_name:
                    client_aliases[project.developer_name] = short
                    aliases_dirty = True

                entry = _project_to_todo_entry(project, client_aliases)
                repo.upsert(entry)
                created += 1

        except Exception as e:
            errors.append(f"{project.project_name}: {e}")
            logger.warning("Sync error for %s: %s", project.project_name, e)

    # Persist any new alias entries
    if aliases_dirty:
        _save_client_aliases(client_aliases)
        logger.info("Updated client_aliases with %d entries", len(client_aliases))

    logger.info("ClickUp sync: %d created, %d updated, %d errors", created, updated, len(errors))
    return {
        "provisioned_count": len(provisioned),
        "created": created,
        "updated": updated,
        "errors": errors,
    }


async def sync_with_stage_report() -> dict[str, Any]:
    """Sync with live ClickUp task status via stage_monitor.

    Fetches actual task completion from ClickUp to determine current stage,
    derives next steps from the dependency graph, and updates To Do entries.
    Formats output to match the original .docx style (bold-label paragraphs,
    no structured stage output).
    """
    from autohelper.modules.projects.service import list_projects
    from autohelper.modules.projects.stage_monitor import get_project_stage_report
    from autohelper.modules.projects.template_resolver import resolve_template
    from autohelper.modules.projects.types import ProjectStatus
    from .pipeline.repo import BfaProjectRepo

    repo = BfaProjectRepo()
    all_projects = list_projects()
    provisioned = [p for p in all_projects if p.status in (ProjectStatus.PROVISIONED, ProjectStatus.ACTIVE)]

    client_aliases = _load_client_aliases()

    updated = 0
    errors: list[str] = []

    for project in provisioned:
        if not project.clickup_list_id:
            continue
        try:
            report = await get_project_stage_report(project)
            manifest = resolve_template(project.intake)

            existing = _find_existing_entry(repo, project.project_name, project.developer_name)
            if not existing:
                existing = _project_to_todo_entry(project, client_aliases)

            sections = existing.get("sections", {})

            # -- Update phase from stage report --
            if report.current_stage and report.stages:
                stage = next((s for s in report.stages if s.number == report.current_stage), None)
                if stage:
                    existing["bfa_phase_canonical"] = stage.name
                    existing["bfa_phase_display"] = stage.name
                    sections["bfa_phase"] = _build_phase_section(stage.name)

            # -- Derive next steps from dependency graph --
            completed_ids = {t.temp_id for t in report.tasks if t.is_complete}
            ready_tasks = []
            for task in manifest.tasks:
                if task.temp_id in completed_ids:
                    continue
                deps = task.depends_on or []
                unmet = [d for d in deps if d not in completed_ids]
                if not unmet:
                    ready_tasks.append(task)

            if ready_tasks:
                task_names = [t.name for t in ready_tasks]
                sections["next_steps"] = _build_next_steps_section(task_names)

            # -- Remove milestones section (not in original format) --
            sections.pop("milestones", None)

            existing["sections"] = sections
            repo.upsert(existing)
            updated += 1

        except Exception as e:
            errors.append(f"{project.project_name}: {e}")
            logger.warning("Stage sync error for %s: %s", project.project_name, e)

    return {"updated": updated, "errors": errors}
