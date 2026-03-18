"""
Pass 1b: Clean, align, and validate imported project data.
Produces final YAML-ready project modules.
"""

import re
from lxml import html as lxml_html
from lxml import etree
from . import config, utils
from .style_resolver import walk_html_for_runs

# Canonical display order for project sections
SECTION_DISPLAY_ORDER = [
    "contacts",
    "artists",
    "artwork_title",
    "bfa_phase",
    "next_steps",
    "governance",
    "milestones",
    "fabrication",
    "unmapped",
]

# Regex: line that is ONLY a label (with optional colon), no value after it
_EMPTY_LABEL_RE = re.compile(
    r"^[\w\s/#&.,()'+\-]+:\s*$"
)


def _is_empty_label(text):
    """True if the text is just a field label with no value."""
    text = text.strip()
    if not text:
        return True
    if _EMPTY_LABEL_RE.match(text):
        return True
    # Bare label without colon (e.g. "PPAP")
    clean = text.lower().rstrip(":").strip()
    if clean in config.SECTION_LABELS:
        return True
    return False


def _strip_empty_labels_html(html_str):
    """Remove paragraphs that are just empty labels from section HTML."""
    if not html_str or not html_str.strip():
        return html_str

    try:
        doc = lxml_html.fromstring(f"<div>{html_str}</div>")
    except Exception:
        return html_str

    to_remove = []
    for el in doc.iter():
        if el.tag in ("p", "h4", "h5", "h6"):
            text = el.text_content().strip()
            if _is_empty_label(text):
                to_remove.append(el)

    for el in to_remove:
        parent = el.getparent()
        if parent is not None:
            parent.remove(el)

    result = etree.tostring(doc, method="html", encoding="unicode")
    if result.startswith("<div>"):
        result = result[5:]
    if result.endswith("</div>"):
        result = result[:-6]
    return result.strip()


def _strip_empty_labels_text(text):
    """Remove lines that are just empty labels from section text."""
    if not text:
        return text
    lines = text.split("\n")
    cleaned = [line for line in lines if not _is_empty_label(line)]
    return "\n".join(cleaned)


# Patterns that indicate budget/money text leaked into the city field
_CITY_BUDGET_RE = re.compile(
    r"\s*(?:Art(?:work)?|Total|Fee)\s*[:=].*$", re.IGNORECASE
)
_CITY_PAREN_BUDGET_RE = re.compile(
    r"\s*\([^)]*(?:Art|Total|Fee|\$)[^)]*\)\s*\$?[\d,]*\.?\d*\s*$", re.IGNORECASE
)
_CITY_PAREN_MONEY_RE = re.compile(
    r"\s*\(\s*\$[\d,]+(?:\.\d+)?\s*\)\s*$"
)

# Team code normalization: fix formatting inconsistencies
TEAM_ALIASES = {
    "J/": "J",
    "AC/ NM": "AC/NM",
    "JB + NM": "JB/NM",
}


def _clean_city(city):
    """Strip budget text, stray parens, and other contaminants from city."""
    if not city or city == "TBC":
        return city
    # Remove parenthesized budget fragments: "(Artwork: | Total:) $275,000"
    city = _CITY_PAREN_BUDGET_RE.sub("", city)
    # Remove bare money in parens: "($250,000.00)"
    city = _CITY_PAREN_MONEY_RE.sub("", city)
    # Remove unparenthesized budget tail: "Burnaby Art: $165K Total: $204,518"
    city = _CITY_BUDGET_RE.sub("", city)
    # Strip stray trailing parens: "BC)" → "BC"
    city = city.rstrip(")").strip()
    # If the result looks like it was entirely budget data, mark TBC
    if not city or city.startswith("$") or city.lower().startswith("total"):
        return "TBC"
    return city


def _normalize_team(team):
    """Normalize team code formatting."""
    if not team:
        return team
    if team in TEAM_ALIASES:
        return TEAM_ALIASES[team]
    # Normalize whitespace around slashes: "AC/ NM" → "AC/NM"
    team = re.sub(r"\s*/\s*", "/", team)
    # Strip trailing slash: "J/" → "J"
    team = team.rstrip("/")
    # Normalize " + " to "/": "JB + NM" → "JB/NM"
    team = re.sub(r"\s*\+\s*", "/", team)
    return team


def _reorder_sections(sections):
    """Return sections dict in canonical display order."""
    ordered = {}
    for key in SECTION_DISPLAY_ORDER:
        if key in sections:
            ordered[key] = sections[key]
    for key in sections:
        if key not in ordered:
            ordered[key] = sections[key]
    return ordered


def _parse_next_steps(sections):
    steps = []
    ns_data = sections.get("next_steps", {})
    text = ns_data.get("text", "")
    html = ns_data.get("html", "")

    if not text.strip():
        return steps

    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    bullets = []
    for line in lines:
        clean = re.sub(r"^[•·\-\*]\s*", "", line).strip()
        if clean:
            sub = [s.strip() for s in clean.split("•") if s.strip()]
            bullets.extend(sub)

    for b in bullets:
        date_match = re.search(r"\(([^)]+)\)\s*$", b)
        date_display = "TBC"
        date_iso = "TBC"
        text_part = b

        if date_match:
            d_str = date_match.group(1).strip()
            dd, di = utils.normalize_date(d_str)
            if di != "TBC":
                date_display = dd
                date_iso = di
                text_part = b[: date_match.start()].strip()

        steps.append(
            {"text": text_part, "date_display": date_display, "date_iso": date_iso}
        )

    return steps


def process_project(imported, resolver=None):
    if imported["type"] in ("preamble", "preamble-lists"):
        return {
            "uid": imported["uid"],
            "slug": imported["slug"],
            "fingerprint": imported["fingerprint"],
            "type": imported["type"],
            "fields": {},
            "sections": imported["sections"],
            "next_steps": [],
            "bfa_phase_canonical": None,
        }

    fields = imported["fields"].copy()

    # Clean city field (strip leaked budget text, stray parens)
    if "city" in fields:
        fields["city"] = _clean_city(fields["city"])

    # Normalize team code formatting
    if "owner_team" in fields:
        fields["owner_team"] = _normalize_team(fields["owner_team"])

    sections = imported["sections"]

    contacts_text = sections.get("contacts", {}).get("text", "")
    artists_text = sections.get("artists", {}).get("text", "")

    phase_text = sections.get("bfa_phase", {}).get("text", "")
    phase_canonical = utils.canonicalize_phase(phase_text) if phase_text else "TBC"

    EARLY_PHASES = {"Intake/Scoping", "EOI/Shortlist", "TBC",
                    "1. Project Initiation", "2. PPAP", "3. DPAP",
                    "4.1. Artist Selection SP#1"}

    if not contacts_text.strip():
        contacts_text = "TBC"
    if not artists_text.strip():
        if phase_canonical in EARLY_PHASES:
            artists_text = "TBD"
        else:
            artists_text = "TBC"

    next_steps = _parse_next_steps(sections)

    cleaned_sections = _reorder_sections({
        key: sec
        for key, val in sections.items()
        for sec in [{
            "text": _strip_empty_labels_text(val.get("text", "")),
            "html": _strip_empty_labels_html(
                utils.normalize_html_whitespace(val.get("html", ""))
            ),
        }]
        if sec["text"].strip() or sec["html"].strip()
    })

    # Compute styled runs per section (in-memory, not persisted to YAML)
    if resolver:
        for sec_data in cleaned_sections.values():
            html = sec_data.get("html", "")
            if html.strip():
                sec_data["runs"] = walk_html_for_runs(html, resolver)

    return {
        "uid": imported["uid"],
        "slug": imported["slug"],
        "fingerprint": imported["fingerprint"],
        "type": "project",
        "fields": fields,
        "sections": cleaned_sections,
        "header": {
            "text": imported["header"]["text"],
            "html": utils.normalize_html_whitespace(imported["header"]["html"]),
        },
        "contacts_text": contacts_text,
        "artists_text": artists_text,
        "bfa_phase_display": phase_text or "TBC",
        "bfa_phase_canonical": phase_canonical,
        "next_steps": next_steps,
        "status": imported.get("status", "active"),
    }


def derive_metadata(project):
    """Derive filter-facing metadata from sections (the source of truth).

    Returns a dict with bfa_phase_canonical, contacts_text, artists_text,
    next_steps — all computed from section data, not stored separately.
    """
    sections = project.get("sections", {})

    # Phase
    phase_text = sections.get("bfa_phase", {}).get("text", "")
    phase_canonical = utils.canonicalize_phase(phase_text) if phase_text else "TBC"
    # If section is empty, fall back to legacy top-level key (migration path)
    if phase_canonical == "TBC":
        phase_canonical = project.get("bfa_phase_canonical", "TBC")

    # Contacts
    contacts_text = sections.get("contacts", {}).get("text", "")
    if not contacts_text.strip():
        contacts_text = project.get("contacts_text", "TBC")

    # Artists
    artists_text = sections.get("artists", {}).get("text", "")
    if not artists_text.strip():
        artists_text = project.get("artists_text", "TBC")

    # Next steps
    next_steps = _parse_next_steps(sections)

    return {
        "bfa_phase_canonical": phase_canonical,
        "contacts_text": contacts_text or "TBC",
        "artists_text": artists_text or "TBC",
        "next_steps": next_steps,
    }


# Sections that contain project-specific data editable in the composition view
EDITABLE_SECTIONS = {
    "contacts", "artists", "artwork_title", "next_steps",
    "governance", "milestones", "fabrication", "unmapped",
}

SECTION_LABELS_DISPLAY = {
    "contacts": "Contacts",
    "artists": "Artists",
    "artwork_title": "Artwork Title",
    "bfa_phase": "Phase",
    "next_steps": "Next Steps",
    "governance": "Governance",
    "milestones": "Milestones",
    "fabrication": "Fabrication",
    "unmapped": "Other",
}


def get_section_meta(sections):
    """Return editability metadata for each section.

    All sections with project-specific content are editable as text.
    Structured metadata (phase, contacts, etc.) is derived from the
    edited text via fuzzymatch on save — no special UI controls needed.
    """
    meta = {}
    for sec_name in sections:
        meta[sec_name] = {
            "editable": sec_name in EDITABLE_SECTIONS or sec_name == "bfa_phase",
            "label": SECTION_LABELS_DISPLAY.get(sec_name, sec_name),
        }
    return meta


def migrate_project_phase(project):
    """Migrate a project's phase from old 9-phase to new 12-phase system.

    Modifies the project dict in-place if migration is needed.
    Returns True if the phase was migrated.
    """
    old_phase = project.get("bfa_phase_canonical")
    if not old_phase or old_phase == "TBC":
        return False
    # Already new-style?
    if old_phase in config.VALID_PHASES:
        return False
    new_phase = utils.migrate_phase(old_phase)
    if new_phase != old_phase:
        project["bfa_phase_canonical"] = new_phase
        return True
    return False


def process_excel_project(project):
    """Process a project that was created from Excel import (no HTML sections).

    Generates minimal HTML from structured text fields for rendering.
    """
    if project.get("source") != "excel":
        return project

    # Generate basic section HTML from text fields
    contacts_text = project.get("contacts_text", "TBC")
    artists_text = project.get("artists_text", "TBD")

    if contacts_text and contacts_text != "TBC":
        lines = contacts_text.split("\n")
        html_lines = [f"<p>{_text_to_html(ln)}</p>" for ln in lines if ln.strip()]
        project.setdefault("sections", {})["contacts"] = {
            "text": contacts_text,
            "html": "\n".join(html_lines),
        }

    if artists_text and artists_text not in ("TBC", "TBD"):
        lines = artists_text.split("\n")
        html_lines = [f"<p>{_text_to_html(ln)}</p>" for ln in lines if ln.strip()]
        project.setdefault("sections", {})["artists"] = {
            "text": artists_text,
            "html": "\n".join(html_lines),
        }

    phase = project.get("bfa_phase_canonical", "TBC")
    if phase and phase != "TBC":
        project.setdefault("sections", {})["bfa_phase"] = {
            "text": phase,
            "html": f'<p><strong>Project Status:</strong> {phase}</p>',
        }

    return project


def _text_to_html(text):
    """Minimal text-to-HTML conversion (escape + bold labels)."""
    import html as html_mod
    text = html_mod.escape(text)
    # Bold labels like "Contact:" or "Architect:"
    text = re.sub(
        r"^(\w[\w\s]*:)",
        r"<strong>\1</strong>",
        text,
    )
    return text
