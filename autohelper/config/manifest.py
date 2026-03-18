"""
Settings manifest — single source of truth for all user-editable settings.

Every field that appears in config.json AND the Settings class is defined here.
The dashboard, ConfigStore defaults, Settings loader, and backend poller all
derive their field lists from this manifest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FieldDef:
    """Definition of a single user-editable setting."""

    key: str  # config.json key AND Settings attribute name
    label: str  # UI label
    section: str  # "general" | "mail" | "contacts" | "exchange"
    field_type: str  # "bool" | "int" | "string" | "select" | "text" | "string_list" | "tag_list"
    default: Any  # Default value
    description: str = ""
    admin_only: bool = False
    min_value: int | None = None
    max_value: int | None = None
    options: list[str] | None = None  # For "select" type
    placeholder: str = ""
    depends_on: str | None = None  # Key of bool field; hide unless True
    row_group: str | None = None  # Same group -> side-by-side in UI


# =============================================================================
# Field Definitions
# =============================================================================

FIELDS: tuple[FieldDef, ...] = (
    # -- General --
    FieldDef(
        key="allowed_roots",
        label="Allowed Roots",
        section="general",
        field_type="string_list",
        default=[],
        description="Filesystem paths to index (one per line)",
        placeholder="/path/to/folder",
    ),
    FieldDef(
        key="excludes",
        label="Excludes",
        section="general",
        field_type="tag_list",
        default=["pyc", "__pycache__", ".git", ".idea", "node_modules"],
        description="Patterns to exclude from indexing (comma-separated)",
    ),
    FieldDef(
        key="log_level",
        label="Log Level",
        section="general",
        field_type="select",
        default="INFO",
        options=["DEBUG", "INFO", "WARNING", "ERROR"],
    ),
    # -- Mail --
    FieldDef(
        key="mail_enabled",
        label="Enable mail polling",
        section="mail",
        field_type="bool",
        default=False,
    ),
    FieldDef(
        key="mail_poll_interval",
        label="Poll Interval (seconds)",
        section="mail",
        field_type="int",
        default=30,
        min_value=5,
        max_value=3600,
        depends_on="mail_enabled",
    ),
    # -- Contacts --
    FieldDef(
        key="contact_sync_enabled",
        label="Enable contact sync",
        section="contacts",
        field_type="bool",
        default=False,
    ),
    FieldDef(
        key="contact_sync_csv_path",
        label="CSV File Path",
        section="contacts",
        field_type="string",
        default="",
        placeholder=r"C:\path\to\master_contacts.csv",
        depends_on="contact_sync_enabled",
    ),
    FieldDef(
        key="contact_sync_interval_minutes",
        label="Interval (minutes)",
        section="contacts",
        field_type="int",
        default=30,
        min_value=5,
        max_value=1440,
        depends_on="contact_sync_enabled",
        row_group="schedule",
    ),
    FieldDef(
        key="contact_sync_work_hours_start",
        label="Work Hours Start",
        section="contacts",
        field_type="int",
        default=8,
        min_value=0,
        max_value=23,
        depends_on="contact_sync_enabled",
        row_group="schedule",
    ),
    FieldDef(
        key="contact_sync_work_hours_end",
        label="Work Hours End",
        section="contacts",
        field_type="int",
        default=18,
        min_value=0,
        max_value=23,
        depends_on="contact_sync_enabled",
        row_group="schedule",
    ),
    FieldDef(
        key="contact_sync_timezone",
        label="Timezone",
        section="contacts",
        field_type="string",
        default="America/Los_Angeles",
        placeholder="America/Los_Angeles",
        depends_on="contact_sync_enabled",
    ),
    FieldDef(
        key="contact_sync_batch_size",
        label="Batch Size",
        section="contacts",
        field_type="int",
        default=50,
        min_value=1,
        max_value=500,
        depends_on="contact_sync_enabled",
        row_group="batch",
    ),
    FieldDef(
        key="contact_sync_managed_prefix",
        label="Managed Prefix",
        section="contacts",
        field_type="string",
        default="BFA-",
        placeholder="BFA-",
        depends_on="contact_sync_enabled",
        row_group="batch",
    ),
    FieldDef(
        key="contact_sync_dry_run",
        label="Dry run (no Exchange changes)",
        section="contacts",
        field_type="bool",
        default=False,
        depends_on="contact_sync_enabled",
    ),
    # -- Exchange --
    FieldDef(
        key="exchange_email",
        label="Email",
        section="exchange",
        field_type="string",
        default="",
        placeholder="admin@yourdomain.com",
        description="Exchange Online admin email (UPN)",
    ),
    FieldDef(
        key="exchange_password",
        label="Password",
        section="exchange",
        field_type="password",
        default="",
        placeholder="••••••••",
        description="Exchange Online password",
    ),
    # -- ClickUp --
    FieldDef(
        key="clickup_token",
        label="API Token",
        section="clickup",
        field_type="password",
        default="",
        description="ClickUp personal API token (pk_...)",
        placeholder="pk_...",
    ),
    FieldDef(
        key="clickup_workspace_id",
        label="Workspace ID",
        section="clickup",
        field_type="string",
        default="",
        placeholder="9014240887",
        depends_on="clickup_token",
    ),
    FieldDef(
        key="clickup_space_id",
        label="Space ID",
        section="clickup",
        field_type="string",
        default="",
        placeholder="90140886432",
        depends_on="clickup_token",
    ),
    FieldDef(
        key="clickup_list_id",
        label="Template List ID",
        section="clickup",
        field_type="string",
        default="",
        placeholder="901414366813",
        depends_on="clickup_token",
        description="BFA project template list",
    ),
    FieldDef(
        key="clickup_sync_enabled",
        label="Enable template sync",
        section="clickup",
        field_type="bool",
        default=False,
        depends_on="clickup_token",
    ),
    FieldDef(
        key="clickup_sync_interval_hours",
        label="Sync Interval (hours)",
        section="clickup",
        field_type="int",
        default=6,
        min_value=1,
        max_value=168,
        depends_on="clickup_sync_enabled",
    ),
    FieldDef(
        key="clickup_artist_list_id",
        label="Artist List ID",
        section="clickup",
        field_type="string",
        default="",
        placeholder="901400000000",
        depends_on="clickup_token",
        description="ClickUp list ID for artist records",
    ),
    # -- Artists --
    # -- Submissions --
    FieldDef(
        key="image_allowed_roots",
        label="Image Folders",
        section="submissions",
        field_type="string_list",
        default=[],
        description="Directories the image proxy is allowed to serve",
        placeholder="E:/path/to/image/folder",
    ),
    FieldDef(
        key="report_thumbnail_max_area",
        label="Thumbnail Max Area (px)",
        section="submissions",
        field_type="int",
        default=15000,
        min_value=1000,
        max_value=500000,
        description="Max pixel area (w\u00d7h) for report thumbnails",
        row_group="report_thumbs",
    ),
    FieldDef(
        key="report_thumbnail_quality",
        label="Thumbnail Quality",
        section="submissions",
        field_type="int",
        default=80,
        min_value=10,
        max_value=100,
        description="JPEG quality for report thumbnails",
        row_group="report_thumbs",
    ),
    FieldDef(
        key="export_output_dir",
        label="Export Output Directory",
        section="submissions",
        field_type="string",
        default="",
        description="Directory for CSV exports. Leave empty for default (data_dir/exports/).",
        placeholder="C:\\path\\to\\exports",
    ),
    # -- Artists --
    FieldDef(
        key="artist_storage_root",
        label="Storage Root",
        section="artists",
        field_type="string",
        default="",
        description="Company file storage root (e.g. OneDrive sync folder)",
        placeholder=r"C:\Users\you\OneDrive\Company Files",
    ),
    FieldDef(
        key="artist_ground_truth_csv",
        label="Ground Truth CSV",
        section="artists",
        field_type="string",
        default="",
        description="Path to ground truth CSV for artist reconciliation",
        placeholder=r"C:\path\to\final_7450_full.csv",
    ),
    FieldDef(
        key="artist_scan_enabled",
        label="Enable artist scanning",
        section="artists",
        field_type="bool",
        default=False,
    ),
    FieldDef(
        key="artist_scan_on_change",
        label="Auto-rescan on file change",
        section="artists",
        field_type="bool",
        default=True,
        depends_on="artist_scan_enabled",
        description="Watchdog monitors storage root and rescans changed artist folders",
    ),
)


# =============================================================================
# Derived Lookups (computed once at import time)
# =============================================================================

CONFIG_KEYS: list[str] = [f.key for f in FIELDS]

DEFAULTS: dict[str, Any] = {f.key: f.default for f in FIELDS}

FIELDS_BY_KEY: dict[str, FieldDef] = {f.key: f for f in FIELDS}

FIELDS_BY_SECTION: dict[str, list[FieldDef]] = {}
for _f in FIELDS:
    FIELDS_BY_SECTION.setdefault(_f.section, []).append(_f)

@dataclass(frozen=True)
class ActionDef:
    """A section-level action button (e.g. 'Test Connection')."""

    label: str  # Button text
    endpoint: str  # API endpoint to call (POST)
    id: str  # HTML element id
    status_key: str = ""  # If set, add a status div with this id


# Ordered section definitions for UI rendering
@dataclass(frozen=True)
class SectionDef:
    id: str
    label: str
    actions: tuple[ActionDef, ...] = ()


SECTIONS: tuple[SectionDef, ...] = (
    SectionDef(id="general", label="General Settings"),
    SectionDef(id="mail", label="Mail Settings"),
    SectionDef(id="contacts", label="Contact Sync"),
    SectionDef(
        id="exchange",
        label="Exchange Connection",
        actions=(
            ActionDef(
                label="Test Connection",
                endpoint="/contacts/exchange/test",
                id="btn-exchange-test",
                status_key="exchange-status",
            ),
        ),
    ),
    SectionDef(
        id="clickup",
        label="ClickUp Integration",
        actions=(
            ActionDef(
                label="Test Connection",
                endpoint="/clickup/validate",
                id="btn-clickup-test",
                status_key="clickup-status",
            ),
        ),
    ),
    SectionDef(id="submissions", label="Submissions"),
    SectionDef(id="artists", label="Artist Records"),
)

SECTION_LABELS: dict[str, str] = {s.id: s.label for s in SECTIONS}
SECTIONS_BY_ID: dict[str, SectionDef] = {s.id: s for s in SECTIONS}


def schema_as_dict() -> dict[str, Any]:
    """Serialize the manifest as a JSON-friendly dict for the /config/schema endpoint."""
    sections = []
    for sec in SECTIONS:
        fields = FIELDS_BY_SECTION.get(sec.id, [])
        admin_only = any(f.admin_only for f in fields) and all(f.admin_only for f in fields)
        entry: dict[str, Any] = {
            "id": sec.id,
            "label": sec.label,
            "admin_only": admin_only,
            "fields": [_field_to_dict(f) for f in fields],
        }
        if sec.actions:
            entry["actions"] = [
                {
                    "label": a.label,
                    "endpoint": a.endpoint,
                    "id": a.id,
                    **({"status_key": a.status_key} if a.status_key else {}),
                }
                for a in sec.actions
            ]
        sections.append(entry)
    return {"sections": sections}


def _field_to_dict(f: FieldDef) -> dict[str, Any]:
    """Serialize a single FieldDef to a JSON-friendly dict."""
    d: dict[str, Any] = {
        "key": f.key,
        "label": f.label,
        "type": f.field_type,
        "default": f.default,
    }
    if f.description:
        d["description"] = f.description
    if f.admin_only:
        d["admin_only"] = True
    if f.min_value is not None:
        d["min"] = f.min_value
    if f.max_value is not None:
        d["max"] = f.max_value
    if f.options is not None:
        d["options"] = f.options
    if f.placeholder:
        d["placeholder"] = f.placeholder
    if f.depends_on:
        d["depends_on"] = f.depends_on
    if f.row_group:
        d["row_group"] = f.row_group
    return d
