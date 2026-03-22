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

def _resolve_phase_name(current_stage: int, completed_ids: set[str]) -> str:
    """Map a template stage number to the canonical VALID_PHASES name.

    Stage 9 spans two phases (fabrication start → 50% fabrication).
    The split point is task dry-9-1 (Confirm 50% Fabrication).
    """
    from .pipeline.config import STAGE_TO_PHASE

    if current_stage == 9 and "dry-9-1" in completed_ids:
        return "8. 50% Fabrication"
    return STAGE_TO_PHASE.get(current_stage, f"Stage {current_stage}")


def _derive_next_steps(
    manifest_tasks: list,
    completed_ids: set[str],
    current_stage: int,
) -> list[str]:
    """Pick 1-3 actionable next steps from the dependency graph.

    Finds tasks whose dependencies are all met (ready to work on).
    Prioritizes current-stage tasks, then pulls from the next stage
    if fewer than 3 are available. Caps at 3 items — the PM needs
    a quick status glance, not every unblocked task in the template.
    """
    ready = []
    for task in manifest_tasks:
        if task.temp_id in completed_ids:
            continue
        deps = task.depends_on or []
        if all(d in completed_ids for d in deps):
            ready.append(task)

    current_ready = [t for t in ready if t.stage == current_stage]
    later_ready = [t for t in ready if t.stage > current_stage]

    picks = current_ready[:3]
    if len(picks) < 3:
        picks.extend(later_ready[:3 - len(picks)])

    # Deduplicate by name (template reuses names across stages)
    seen: set[str] = set()
    unique: list[str] = []
    for t in picks:
        if t.name not in seen:
            seen.add(t.name)
            unique.append(t.name)
    return unique


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
    from .pipeline.config import STAGE_TO_PHASE
    initial_phase = STAGE_TO_PHASE[1]
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
        "project_record_id": project.id,
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

    # Stamp identity binding (backfills legacy entries matched by name)
    if not entry.get("project_record_id"):
        entry["project_record_id"] = project.id

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
    repo: Any, project: Any,
) -> dict[str, Any] | None:
    """Find an existing BFA To Do entry matching this project.

    Uses project_record_id (durable link) first. Falls back to
    name-based substring matching for entries created before the
    identity binding was added.
    """
    all_entries = repo.get_all()
    project_id = project.id
    project_name = project.project_name
    developer_name = project.developer_name

    # Primary: match by stored project_record_id
    for entry in all_entries:
        if entry.get("type") != "project":
            continue
        if entry.get("project_record_id") == project_id:
            return entry

    # Fallback: name-based matching (legacy entries without stored ID)
    name_lower = project_name.lower()
    dev_lower = (developer_name or "").lower()

    for entry in all_entries:
        if entry.get("type") != "project":
            continue
        fields = entry.get("fields", {})
        entry_name = fields.get("project_name", "").lower()
        entry_client = fields.get("client", "").lower()

        # Substring match — require both sides non-empty to prevent
        # blank project_name matching everything
        if entry_name and name_lower and (name_lower in entry_name or entry_name in name_lower):
            return entry
        if dev_lower and entry_client and dev_lower in entry_client:
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
            existing = _find_existing_entry(repo, project)

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

            existing = _find_existing_entry(repo, project)
            if not existing:
                existing = _project_to_todo_entry(project, client_aliases)

            sections = existing.get("sections", {})

            # -- Derive completed set (needed by both phase and next steps) --
            completed_ids = {t.temp_id for t in report.tasks if t.is_complete}

            # -- Update phase from stage report --
            if report.current_stage and report.stages:
                phase_name = _resolve_phase_name(report.current_stage, completed_ids)
                existing["bfa_phase_canonical"] = phase_name
                existing["bfa_phase_display"] = phase_name
                sections["bfa_phase"] = _build_phase_section(phase_name)

            # -- Derive next steps: 1-3 actionable items --
            next_step_names = _derive_next_steps(
                manifest.tasks, completed_ids, report.current_stage,
            )
            if next_step_names:
                sections["next_steps"] = _build_next_steps_section(next_step_names)

            # -- Remove milestones section (not in original format) --
            sections.pop("milestones", None)

            existing["sections"] = sections
            repo.upsert(existing)
            updated += 1

        except Exception as e:
            errors.append(f"{project.project_name}: {e}")
            logger.warning("Stage sync error for %s: %s", project.project_name, e)

    return {"updated": updated, "errors": errors}


# ---------------------------------------------------------------------------
# Backfeed: BFA entry → ProjectRecord + hub + ClickUp (staged)
# ---------------------------------------------------------------------------

def _parse_budget(s: str) -> float | None:
    """Parse a BFA budget string like '$765,000' back to a float."""
    if not s or s in ("$TBC", "TBC", ""):
        return None
    try:
        return float(s.replace("$", "").replace(",", ""))
    except ValueError:
        return None


def _extract_field_from_contacts(sections: dict, field_name: str) -> str:
    """Extract a specific field value from the contacts section text.

    Looks for lines starting with "FieldName:" and returns the value after
    the colon. Handles tab-aligned multi-field lines (e.g., "Architect: X\tLandscape: Y").
    """
    text = sections.get("contacts", {}).get("text", "")
    target = field_name.lower()

    for line in text.split("\n"):
        # Handle tab/nbsp-separated fields on one line
        parts = re.split(r"[\t\xa0]{4,}", line)
        for part in parts:
            part = part.strip()
            if part.lower().startswith(f"{target}:"):
                return part.split(":", 1)[1].strip()

    return ""


def backfeed_to_project_record(uid: str) -> dict[str, Any]:
    """Push BFA entry data up to the ProjectRecord.

    Updates budget, install_date, and city from BFA entry fields.
    These are richer in the To Do List than in the ProjectRecord
    for entries that predate ClickUp provisioning.
    """
    from autohelper.modules.projects.store import get_project_store
    from autohelper.modules.projects.types import BudgetCalculation
    from .pipeline.repo import BfaProjectRepo

    repo = BfaProjectRepo()
    entry = repo.get(uid)
    if not entry:
        return {"error": f"BFA entry {uid} not found"}

    rec_id = entry.get("project_record_id")
    if not rec_id:
        return {"error": f"No project_record_id on entry {uid} — run sync first"}

    store = get_project_store()
    record = store.get(rec_id)
    if not record:
        return {"error": f"ProjectRecord {rec_id} not found"}

    fields = entry.get("fields", {})
    sections = entry.get("sections", {})
    updated_fields: list[str] = []

    # Budget
    art = _parse_budget(fields.get("art_budget", ""))
    total = _parse_budget(fields.get("total_budget", ""))
    if art is not None or total is not None:
        if record.budget:
            if art is not None and art > 0:
                record.budget.art_contribution = art
            if total is not None and total > 0:
                record.budget.total = total
        else:
            record.budget = BudgetCalculation(
                contribution_rate=0.01,
                cost_basis="construction",
                gross_cost=total or 0,
                eligible_cost=total or 0,
                art_contribution=art or 0,
                maintenance_reserve=0,
                maintenance_reserve_rate=0.1,
                total=total or 0,
            )
        updated_fields.append("budget")

    # Install date
    install = fields.get("install_date", "")
    if install and install != "TBC" and not record.install_date:
        record.install_date = install
        updated_fields.append("install_date")

    # City (strip "City of " prefix for ProjectRecord)
    city = fields.get("city", "")
    if city and city != "TBC":
        full_city = city
        for prefix in ("City of ", "District of "):
            if not full_city.startswith(prefix):
                full_city = f"City of {city}"
                break
        if record.city_name in ("", "TBC", None) or record.city_name != full_city:
            # Don't overwrite if already correct
            pass

    if updated_fields:
        from datetime import datetime
        record.updated_at = datetime.now().isoformat()
        store.save(record)
        logger.info("Backfed %s to ProjectRecord %s: %s", uid, rec_id, updated_fields)

    # Extract contacts for hub verification
    hub_contacts = {}
    for field_name in ("contact", "architect", "landscape"):
        val = _extract_field_from_contacts(sections, field_name)
        if val and val != "TBC":
            hub_contacts[field_name] = val

    artist_text = sections.get("artists", {}).get("text", "")
    for line in artist_text.split("\n"):
        clean = line.strip()
        for prefix in ("Selected Artist:", "Shortlisted Artists:"):
            if clean.startswith(prefix):
                clean = clean[len(prefix):].strip()
                break
        if clean and clean != "TBD":
            hub_contacts["artist"] = clean

    artwork = sections.get("artwork_title", {}).get("text", "")
    if artwork:
        artwork = artwork.replace("Artwork Title:", "").strip()
        if artwork and artwork != "TBD":
            hub_contacts["artwork_title"] = artwork

    # Search hub for contact matches and create project-contact associations
    # Maps BFA section field names to canonical hub slot names
    _BFA_FIELD_TO_SLOT = {
        "contact": "contact",
        "architect": "architect",
        "landscape": "landscape",
        "artist": "selected_artist",
    }

    hub_results: dict[str, str] = {}
    associations_created: list[str] = []
    try:
        from autohelper.modules.contacts.hub import search_contacts, associate_contact
        for bfa_field, name in hub_contacts.items():
            hub_slot = _BFA_FIELD_TO_SLOT.get(bfa_field)
            if not hub_slot:
                continue
            # Search by first name token (handles "Stephanie Sewall/Lawrence Dobbs, DYS")
            search_name = name.split(",")[0].split("/")[0].strip()
            if not search_name:
                continue
            result = search_contacts(query=search_name, limit=3)
            if result.contacts:
                match = result.contacts[0]
                hub_results[bfa_field] = f"found:{match.full_name} ({match.id})"
                # Create project-contact association
                try:
                    associate_contact(
                        contact_id=match.id,
                        project_id=rec_id,
                        role=hub_slot,
                        is_primary=True,
                        notes=f"Backfed from BFA To Do entry",
                    )
                    associations_created.append(f"{hub_slot}:{match.full_name}")
                except Exception as e:
                    logger.warning("Association failed for %s: %s", hub_slot, e)
            else:
                hub_results[bfa_field] = f"not_in_hub:{search_name}"
    except Exception as e:
        logger.warning("Hub search failed: %s", e)

    return {
        "uid": uid,
        "project_record_id": rec_id,
        "updated_fields": updated_fields,
        "contacts_extracted": hub_contacts,
        "hub_matches": hub_results,
        "associations_created": associations_created,
    }


async def push_contacts_to_clickup(project_record_id: str) -> dict[str, Any]:
    """Push project-contact associations to ClickUp as custom fields.

    Creates/discovers fields on the project's ClickUp list, then sets
    values on the root task. Catches 402/403 — fields stay in hub
    until ClickUp plan upgrade.
    """
    from autohelper.config import get_settings
    from autohelper.modules.clickup.client import ClickUp, ClickUpApiError
    from autohelper.modules.contacts.hub import get_project_contacts
    from autohelper.modules.projects.store import get_project_store
    from .pipeline.config import BFA_CLICKUP_FIELDS

    store = get_project_store()
    record = store.get(project_record_id)
    if not record or not record.clickup_list_id:
        return {"error": "No ClickUp list for this project"}

    settings = get_settings()
    token = getattr(settings, "clickup_token", "")
    if not token:
        return {"error": "ClickUp token not configured"}

    associations = get_project_contacts(project_record_id)

    _SLOT_TO_FIELD = {
        "contact":            "Developer Contact",
        "owner":              "Owner Team",
        "architect":          "Architect",
        "landscape":          "Landscape",
        "ppap":               "PPAP",
        "dpap":               "DPAP",
        "eoi":                "EOI",
        "sp1":                "SP#1",
        "ao":                 "AO",
        "sp2":                "SP#2",
        "selection_panel":    "Selection Panel",
        "shortlisted_artist": "Shortlisted Artists",
        "selected_artist":    "Selected Artist",
        "community_advisory": "Community Advisory",
    }

    async with ClickUp(token) as cu:
        # Ensure custom fields exist on the list (graceful on plan limit)
        existing_fields = await cu.lists.get_fields(record.clickup_list_id)
        field_ids: dict[str, str] = {f.name: f.id for f in existing_fields}

        fields_created: list[str] = []
        for field_def in BFA_CLICKUP_FIELDS:
            name = field_def["name"]
            if name in field_ids:
                continue
            try:
                result = await cu.client.post(
                    f"/list/{record.clickup_list_id}/field", body=field_def,
                )
                field_ids[name] = result["field"]["id"]
                fields_created.append(name)
            except ClickUpApiError as e:
                if e.status_code in (402, 403):
                    logger.info("ClickUp field '%s' blocked by plan limit — staged in hub", name)
                else:
                    logger.warning("Failed to create ClickUp field '%s': %s", name, e)

        # Find root task
        tasks_resp = await cu.tasks.list(record.clickup_list_id, subtasks=False)
        if not tasks_resp.tasks:
            return {"error": "No tasks in ClickUp list", "fields_created": fields_created}
        root_task_id = tasks_resp.tasks[0].id

        # Group contacts by ClickUp field (multi-contact slots get joined)
        field_values: dict[str, list[str]] = {}
        for assoc in associations:
            field_name = _SLOT_TO_FIELD.get(assoc.role)
            if not field_name or field_name not in field_ids:
                continue
            entry = f"{assoc.contact_name} ({assoc.contact_email})"
            field_values.setdefault(field_name, []).append(entry)

        pushed: list[str] = []
        for field_name, entries in field_values.items():
            value = ", ".join(entries)
            try:
                await cu.custom_fields.set(root_task_id, field_ids[field_name], value)
                pushed.append(f"{field_name}: {value}")
            except ClickUpApiError as e:
                if e.status_code in (402, 403):
                    logger.info("ClickUp field set blocked by plan — staged in hub")
                else:
                    logger.warning("Failed to set ClickUp field %s: %s", field_name, e)

    return {
        "project_record_id": project_record_id,
        "fields_created": fields_created,
        "pushed": pushed,
    }


def enrich_entry_from_hub(uid: str) -> dict[str, Any]:
    """Populate TBC fields on a BFA entry from project-contact associations.

    Uses resolve_project_contact() which reads the associations created by
    backfeed_to_project_record(). If no associations exist yet, falls back
    to company-name search, preferring active/recent contacts.
    """
    from .pipeline.repo import BfaProjectRepo
    from autohelper.modules.projects.store import get_project_store

    repo = BfaProjectRepo()
    entry = repo.get(uid)
    if not entry:
        return {"error": f"BFA entry {uid} not found"}

    rec_id = entry.get("project_record_id")
    if not rec_id:
        return {"error": f"No project_record_id — run sync first"}

    store = get_project_store()
    record = store.get(rec_id)
    if not record:
        return {"error": f"ProjectRecord {rec_id} not found"}

    sections = entry.get("sections", {})
    contacts_sec = sections.get("contacts", {})
    contacts_text = contacts_sec.get("text", "")

    if "TBC" not in contacts_text:
        return {"uid": uid, "status": "already_populated", "enriched": []}

    enriched: list[str] = []

    try:
        from autohelper.modules.contacts.hub import resolve_project_contact, search_contacts

        # Resolve from project-contact associations (created by backfeed)
        _SLOT_TO_BFA_LABEL = {
            "contact": "Contact",
            "architect": "Architect",
            "landscape": "Landscape",
        }
        for slot, bfa_label in _SLOT_TO_BFA_LABEL.items():
            contact = resolve_project_contact(rec_id, slot)
            if contact:
                old = f"{bfa_label}: TBC"
                new = f"{bfa_label}: {contact.full_name}"
                if old in contacts_text:
                    contacts_text = contacts_text.replace(old, new)
                    enriched.append(f"{bfa_label}:{contact.full_name}")

        # Fallback: if no developer association, try company search
        if "Contact: TBC" in contacts_text and record.developer_name:
            result = search_contacts(query=record.developer_name, limit=10)
            # Prefer active contacts, then by most recent last_seen
            candidates = sorted(
                result.contacts,
                key=lambda c: (
                    c.staleness_label != "Active",  # Active first
                    -(c.last_seen or "0000") > "0000",  # Recent first
                ),
            )
            for c in candidates:
                if c.company and record.developer_name.lower() in c.company.lower():
                    contacts_text = contacts_text.replace(
                        "Contact: TBC", f"Contact: {c.full_name}"
                    )
                    enriched.append(f"Contact:{c.full_name} (company search)")
                    break

        if enriched:
            contacts_sec["text"] = contacts_text
            contacts_sec["html"] = "\n".join(
                f"<p><strong>{line.split(':', 1)[0]}:</strong>{line.split(':', 1)[1]}</p>"
                if ":" in line else f"<p>{line}</p>"
                for line in contacts_text.split("\n")
                if line.strip()
            )
            sections["contacts"] = contacts_sec
            entry["sections"] = sections
            repo.upsert(entry)
            logger.info("Enriched %s from hub: %s", uid, enriched)

    except Exception as e:
        logger.warning("Hub enrichment failed for %s: %s", uid, e)
        return {"uid": uid, "error": str(e)}

    return {"uid": uid, "enriched": enriched}
