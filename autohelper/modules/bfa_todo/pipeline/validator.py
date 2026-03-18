"""BFA Todo validation engine.

Runs consistency checks on project fields and returns typed diagnostics.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any


# ---------------------------------------------------------------------------
# Canonical values
# ---------------------------------------------------------------------------

KNOWN_CITIES = {
    "Vancouver", "North Vancouver", "Burnaby", "New Westminster",
    "Coquitlam", "Port Moody", "Surrey", "Richmond", "Squamish",
    "Victoria", "Edmonton", "Nanaimo", "Musqueam",
}

CITY_ALIASES: dict[str, str] = {
    "N. Van": "North Vancouver",
    "N Van": "North Vancouver",
    "North Van": "North Vancouver",
    "N. Vancouver": "North Vancouver",
    "City of NV": "North Vancouver",
    "Van": "Vancouver",
    "Vancouver BC": "Vancouver",
    "City of Burnaby": "Burnaby",
    "Burnaby BC": "Burnaby",
    "Coquitlam Central": "Coquitlam",
}

KNOWN_TEAMS = {"AC", "NM", "JB", "NY", "JJ", "SE", "EK", "KH", "SF", "ST", "MH", "MM", "BFA"}

# Budget/junk patterns that should never appear in display fields
_BUDGET_RE = re.compile(r"\$|Total|Budget|Artwork:|Art:|Fee", re.IGNORECASE)
_JUNK_RE = re.compile(r"[_]{3,}|[|]|\bBC\b\s*$|\bPENDING\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Diagnostic type
# ---------------------------------------------------------------------------

@dataclass
class Diagnostic:
    field: str
    level: str  # "error" | "warning"
    code: str
    message: str
    suggestion: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Per-project validation
# ---------------------------------------------------------------------------

def validate_project(project: dict[str, Any]) -> list[Diagnostic]:
    """Run all checks on a single project, return diagnostics."""
    diags: list[Diagnostic] = []
    fields = project.get("fields", {})
    sections = project.get("sections", {})

    client = fields.get("client", "TBC")
    project_name = fields.get("project_name", "TBC")
    city = fields.get("city", "TBC")
    owner_team = fields.get("owner_team", "BFA")
    phase = project.get("bfa_phase_canonical", "TBC")
    contacts = sections.get("contacts", {}).get("text", "")
    artists = sections.get("artists", {}).get("text", "")
    install_date = fields.get("install_date", "TBC")

    # --- City checks ---
    if city in ("TBC", "TBD", ""):
        diags.append(Diagnostic("city", "warning", "city_missing", "City is not set"))
    elif city in CITY_ALIASES:
        canonical = CITY_ALIASES[city]
        diags.append(Diagnostic(
            "city", "warning", "city_inconsistent",
            f"City '{city}' — did you mean '{canonical}'?",
            suggestion=canonical,
        ))
    elif city not in KNOWN_CITIES:
        # Check for junk in city field
        if _BUDGET_RE.search(city) or _JUNK_RE.search(city):
            diags.append(Diagnostic(
                "city", "error", "city_junk",
                f"City contains invalid text: '{city}'",
            ))
        elif len(city) > 30:
            diags.append(Diagnostic(
                "city", "warning", "city_unknown",
                f"Unknown city: '{city}'",
            ))

    # --- Client checks ---
    if client in ("TBC", "TBD", ""):
        diags.append(Diagnostic("client", "warning", "client_missing", "Client is not set"))
    elif len(client) > 50:
        diags.append(Diagnostic(
            "client", "warning", "client_long",
            f"Client name is unusually long ({len(client)} chars) — may contain unparsed header text",
        ))
    if _BUDGET_RE.search(client):
        diags.append(Diagnostic(
            "client", "error", "budget_in_client",
            "Client name contains budget text",
        ))

    # --- Project name checks ---
    if project_name in ("TBC", "TBD", ""):
        diags.append(Diagnostic("project_name", "warning", "project_name_missing", "Project name is not set"))
    if _BUDGET_RE.search(project_name):
        diags.append(Diagnostic(
            "project_name", "error", "budget_in_title",
            "Project name contains budget text",
        ))

    # --- Team checks ---
    if owner_team:
        # Teams can be compound: "JB/NY", "AC/NM"
        parts = re.split(r"[/,]", owner_team)
        unknown = [p.strip() for p in parts if p.strip() and p.strip() not in KNOWN_TEAMS]
        if unknown:
            diags.append(Diagnostic(
                "owner_team", "warning", "team_unknown",
                f"Unknown team member(s): {', '.join(unknown)}",
            ))

    # --- Phase checks ---
    from . import config as pipeline_config
    all_phases = set(pipeline_config.VALID_PHASES) | set(pipeline_config.VALID_PHASES_LEGACY)
    if phase in ("TBC", "TBD", ""):
        diags.append(Diagnostic("phase", "warning", "phase_missing", "Phase is not set"))
    elif phase not in all_phases:
        diags.append(Diagnostic(
            "phase", "warning", "phase_unknown",
            f"Unknown phase: '{phase}'",
        ))

    # --- Contacts/Artists checks (phase-dependent) ---
    LATE_PHASES = {"Artist selected", "Contracting", "Design development", "Approvals",
                   "Fabrication", "Install", "Closeout",
                   "5. Artist Contract", "6. Detailed Design", "7. Fabrication Start",
                   "8. 50% Fabrication", "9. 100% Fabrication/Install",
                   "10. Final Documents", "11. Photo"}
    MID_PHASES = {"EOI/Shortlist", "4.1. Artist Selection SP#1", "4.2. Artist Selection SP#2"} | LATE_PHASES

    if phase in MID_PHASES and (not contacts.strip() or contacts.strip() in ("TBC", "TBD")):
        diags.append(Diagnostic(
            "contacts", "warning", "contacts_missing",
            "Contacts not filled for a project past intake",
        ))

    if phase in LATE_PHASES and (not artists.strip() or artists.strip() in ("TBC", "TBD")):
        diags.append(Diagnostic(
            "artists", "warning", "artists_missing",
            "Artists not filled for a project past selection",
        ))

    # --- Install date checks ---
    INSTALL_PHASES = {"Fabrication", "Install", "7. Fabrication Start",
                      "8. 50% Fabrication", "9. 100% Fabrication/Install"}
    if phase in INSTALL_PHASES and (not install_date or install_date.strip() in ("TBC", "TBD", "")):
        diags.append(Diagnostic(
            "install_date", "warning", "install_vague",
            "Install date is TBC for a project in fabrication/install phase",
        ))

    return diags


# ---------------------------------------------------------------------------
# Batch validation (for duplicate detection)
# ---------------------------------------------------------------------------

def validate_all(projects: list[dict[str, Any]]) -> dict[str, list[Diagnostic]]:
    """Validate all projects, including cross-project checks like duplicates.

    Returns {uid: [diagnostics]} for projects that have issues.
    """
    results: dict[str, list[Diagnostic]] = {}

    # Per-project checks
    for p in projects:
        uid = p.get("uid", "")
        diags = validate_project(p)
        if diags:
            results[uid] = diags

    # Cross-project: duplicate client+project_name
    seen: dict[str, str] = {}  # "client|project_name" -> first uid
    for p in projects:
        uid = p.get("uid", "")
        fields = p.get("fields", {})
        client = fields.get("client", "").strip().lower()
        project_name = fields.get("project_name", "").strip().lower()
        if not client or client == "tbc":
            continue
        key = f"{client}|{project_name}"
        if key in seen and seen[key] != uid:
            diag = Diagnostic(
                "client", "warning", "client_duplicate",
                f"Possible duplicate of another project with same client/name",
            )
            results.setdefault(uid, []).append(diag)
        else:
            seen[key] = uid

    return results
