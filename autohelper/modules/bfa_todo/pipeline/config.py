import re
import uuid
from pathlib import Path

from autohelper.shared.paths import data_dir

# All persistent data goes under data_dir() / "bfa_todo"
DATA_DIR = data_dir() / "bfa_todo"
PROJECTS_DIR = DATA_DIR / "projects"
SITE_DIR = DATA_DIR / "site"
ASSETS_DIR = SITE_DIR / "assets"
ALIASES_FILE = DATA_DIR / "aliases.yaml"

# Output directory for .docx and .pdf artifacts
OUTPUT_DIR = Path(
    "E:/OneDrive - Ballard Fine Art"
    "/BALLARD FINE ART - ALL FILES/4. TO DO LIST/2026/_bfa"
)

# Templates are bundled with the package
TEMPLATE_DIR = Path(__file__).parent / "templates"

UUID_NAMESPACE = uuid.UUID("a3b2c1d0-e4f5-6789-abcd-ef0123456789")

HEADER_TAG = "h3"

SECTION_LABELS = {
    "contact": "contacts",
    "contacts": "contacts",
    "team": "contacts",
    "contributor": "contacts",
    "contributors": "contacts",
    "owner": "contacts",
    "governance": "governance",
    "governance / agreement": "governance",
    "agreement": "governance",
    "committee": "governance",
    "jury": "governance",
    "key dates / milestones": "milestones",
    "key dates": "milestones",
    "milestones": "milestones",
    "schedule": "milestones",
    "artist": "artists",
    "artists": "artists",
    "selected artist": "artists",
    "shortlisted artists": "artists",
    "artwork title": "artwork_title",
    "bfa phase": "bfa_phase",
    "phase": "bfa_phase",
    "project status": "bfa_phase",
    "status": "bfa_phase",
    "current phase": "bfa_phase",
    "project phase": "bfa_phase",
    "bfa next steps": "next_steps",
    "next steps": "next_steps",
    "next step": "next_steps",
    "action items": "next_steps",
    "actions": "next_steps",
    "to do": "next_steps",
    "architect": "architect",
    "landscape": "landscape",
    "ppap": "ppap",
    "dpap": "dpap",
    "eoi": "eoi",
    "sp#1": "sp1",
    "sp#2": "sp2",
    "ao": "ao",
    "selection panel": "selection_panel",
    "nvpaac rep": "nvpaac_rep",
    "fabrication 25%": "fabrication",
    "fabrication 50%": "fabrication",
    "fabrication 75%": "fabrication",
    "fabrication 100%": "fabrication",
    "25% fabrication": "fabrication",
    "50% fabrication": "fabrication",
    "75% fabrication": "fabrication",
    "100% fabrication": "fabrication",
    "fabrication": "fabrication",
    "installation": "milestones",
    "final report": "milestones",
    "review of art before delivery": "milestones",
    "storage": "milestones",
    "community advisors": "contacts",
    "community advisory": "contacts",
    "checklist": "contacts",
    "fabricator": "contacts",
    "fabricators": "contacts",
}

# --- Doc-sourced phase canonicalization (old 9-phase system) ---
PHASE_CANON = {
    "scoping": "Intake/Scoping",
    "intake": "Intake/Scoping",
    "eoi": "EOI/Shortlist",
    "shortlist": "EOI/Shortlist",
    "looping": "EOI/Shortlist",
    "selection": "Artist selected",
    "selected": "Artist selected",
    "artist selected": "Artist selected",
    "contract": "Contracting",
    "contracting": "Contracting",
    "concept": "Design development",
    "design": "Design development",
    "detailed design": "Design development",
    "dd": "Design development",
    "design development": "Design development",
    "approvals": "Approvals",
    "fabrication": "Fabrication",
    "install": "Install",
    "installation": "Install",
    "complete": "Closeout",
    "done": "Closeout",
    "closeout": "Closeout",
}

# --- Template stage number → canonical phase name ---
# Bridges bfa_templates.json ALL-CAPS stage names to the numbered
# VALID_PHASES system used by the To Do List and Excel import.
# Stage 9 spans two phases — refined at runtime by _resolve_phase_name().
STAGE_TO_PHASE: dict[int, str] = {
    1:  "1. Project Initiation",
    2:  "2. PPAP",
    3:  "3. DPAP",
    4:  "3. DPAP",                      # Community engagement is part of DPAP phase
    5:  "4.1. Artist Selection SP#1",
    6:  "4.2. Artist Selection SP#2",
    7:  "5. Artist Contract",
    8:  "6. Detailed Design",
    9:  "7. Fabrication Start",         # Refined to "8. 50% Fabrication" if dry-9-1 complete
    10: "9. 100% Fabrication/Install",
    11: "10. Final Documents",
}

# --- New 12-phase canonical system (Excel is ground truth) ---
VALID_PHASES = [
    "1. Project Initiation",
    "2. PPAP",
    "3. DPAP",
    "4.1. Artist Selection SP#1",
    "4.2. Artist Selection SP#2",
    "5. Artist Contract",
    "6. Detailed Design",
    "7. Fabrication Start",
    "8. 50% Fabrication",
    "9. 100% Fabrication/Install",
    "10. Final Documents",
    "11. Photo",
    "TBC",
]

# Old 9-phase names still valid for Doc import (kept for backward compat)
VALID_PHASES_LEGACY = [
    "Intake/Scoping",
    "EOI/Shortlist",
    "Artist selected",
    "Contracting",
    "Design development",
    "Approvals",
    "Fabrication",
    "Install",
    "Closeout",
    "TBC",
]

# Map old 9-phase canonical -> new 12-phase canonical
PHASE_MIGRATION = {
    "Intake/Scoping": "1. Project Initiation",
    "EOI/Shortlist": "4.1. Artist Selection SP#1",
    "Artist selected": "4.2. Artist Selection SP#2",
    "Contracting": "5. Artist Contract",
    "Design development": "6. Detailed Design",
    "Approvals": "6. Detailed Design",
    "Fabrication": "7. Fabrication Start",
    "Install": "9. 100% Fabrication/Install",
    "Closeout": "10. Final Documents",
}

# Map Excel phase text -> canonical phase name
EXCEL_PHASE_MAP = {
    "1. Project Initiation/Fee Proposal": "1. Project Initiation",
    "2. PPAP": "2. PPAP",
    "3. DPAP": "3. DPAP",
    "4.1. Artist Selection SP#1": "4.1. Artist Selection SP#1",
    "4.2. Artist Selection SP#2": "4.2. Artist Selection SP#2",
    "5. Artist Contract": "5. Artist Contract",
    "6. Detailed Design": "6. Detailed Design",
    "7. Fabrication Start": "7. Fabrication Start",
    "8. 50% Fabrication": "8. 50% Fabrication",
    "9. 100% Fabrication/Installation": "9. 100% Fabrication/Install",
    "10. Final Documents": "10. Final Documents",
    "11. Photo": "11. Photo",
}

# Excel column index (1-based) -> field name
EXCEL_COLUMN_MAP = {
    1: "raw_name",           # A: Name
    4: "bfa_lead",           # D: Person
    5: "dp_issuance_date",   # E: DP Issuance Date
    6: "milestone_sp1",      # F: SP1
    7: "artist_orientation",  # G: Artist Orientation
    8: "milestone_sp2",      # H: SP2
    9: "project_kickoff",    # I: Project Kickoff Meeting w/ Artist
    10: "selection_process",  # J: Selection Process
    11: "artist_contract_signed",  # K: Artist Contract Signed
    12: "project_state",     # L: Project State
    13: "project_phase",     # M: Project Phase
    16: "municipality",      # P: Municipality
    17: "address",           # Q: Project Address
    18: "billing_entity",    # R: Billing Entity
    19: "selection_panel",   # S: Selection Panel
    20: "community_advisors",  # T: Community Advisors
    21: "shortlisted_artists",  # U: Shortlisted Artists
    22: "selected_artist",   # V: Artist
    23: "artwork_title",     # W: Artwork Title
    24: "fabricator",        # X: Fabricator
    25: "developer_contact",  # Y: Developer Contact
    26: "architect",         # Z: Architect
    27: "landscape_architect",  # AA: Landscape Architect
    29: "project_budget",    # AC: Project Budget (Total)
    30: "artist_fee",        # AD: Artist Fee/Artwork Budget
    31: "target_completion",  # AE: Target Completion Date
    32: "consultant_fee",    # AF: Consultant Fee
    33: "building_occupancy",  # AG: Building Occupancy
    34: "target_completion_start",  # AH: Target Completion - Start
}

# Excel sheet and row config
EXCEL_SHEET_NAME = "1. current projects overview"
EXCEL_HEADER_ROW = 3
EXCEL_DATA_START_ROW = 4
EXCEL_COMPLETED_DIVIDER = "Completed Projects"

# --- ClickUp custom field schema for project metadata ---
# Staged for deployment when ClickUp plan limit is lifted (FIELD_033).
# _ensure_project_fields() catches 402/403 gracefully.
BFA_CLICKUP_FIELDS = [
    {"name": "Artwork Budget",      "type": "currency", "type_config": {"currency_type": "CAD"}},
    {"name": "Total Budget",        "type": "currency", "type_config": {"currency_type": "CAD"}},
    {"name": "Install Date",        "type": "short_text", "type_config": {}},
    # Contact slots
    {"name": "Developer Contact",   "type": "short_text", "type_config": {}},
    {"name": "Owner Team",          "type": "short_text", "type_config": {}},
    {"name": "Architect",           "type": "short_text", "type_config": {}},
    {"name": "Landscape",           "type": "short_text", "type_config": {}},
    {"name": "PPAP",                "type": "short_text", "type_config": {}},
    {"name": "DPAP",                "type": "short_text", "type_config": {}},
    {"name": "EOI",                 "type": "short_text", "type_config": {}},
    {"name": "SP#1",                "type": "short_text", "type_config": {}},
    {"name": "AO",                  "type": "short_text", "type_config": {}},
    {"name": "SP#2",                "type": "short_text", "type_config": {}},
    {"name": "Selection Panel",     "type": "short_text", "type_config": {}},
    {"name": "Shortlisted Artists", "type": "short_text", "type_config": {}},
    {"name": "Selected Artist",     "type": "short_text", "type_config": {}},
    {"name": "Community Advisory",  "type": "short_text", "type_config": {}},
    {"name": "Artwork Title",       "type": "short_text", "type_config": {}},
]

INLINE_FIELD_LABELS = [
    "architect", "landscape", "owner", "ppap", "dpap", "eoi",
    "sp#1", "sp#2", "ao", "selection panel", "nvpaac rep",
    "shortlisted artists", "selected artist", "artwork title",
    "project status",
]
