"""
DOCX template engine — renders .docx templates via docxtpl (Jinja2-in-Word).

Templates live on OneDrive at:
    PA PROCEDURES/_bfa/templates/

Output goes to:
    data_dir()/documents/<template_key>/<versioned_filename>.docx

Merge context comes from:
    - Contact hub (resolve_merge_fields + per-role contact details)
    - Project intake (project name, address, city, etc.)
    - Runtime fields (dates, one-off values)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from docxtpl import DocxTemplate

from autohelper.shared.paths import data_dir

logger = logging.getLogger(__name__)


# ── Configuration ───────────────────────────────────────────────

# Default template directory — OneDrive path, overridable
DEFAULT_TEMPLATE_DIR = Path(
    r"C:\Users\silen\OneDrive - Ballard Fine Art"
    r"\BALLARD FINE ART - ALL FILES\6. PA PROCEDURES\_bfa\templates"
)


@dataclass
class TemplateInfo:
    """Metadata about an available template."""
    key: str  # filename stem, e.g. "artwork_acceptance"
    name: str  # human-readable, e.g. "Artwork Acceptance"
    path: Path
    fields: list[str]  # merge fields discovered by docxtpl


@dataclass
class RenderResult:
    """Result of rendering a template."""
    output_path: Path
    filename: str
    template_key: str
    generated_at: str
    unfilled: list[str]  # fields that had no value provided


# ── Template Discovery ──────────────────────────────────────────


def _humanize(key: str) -> str:
    """Convert filename stem to readable name: 'artwork_acceptance' → 'Artwork Acceptance'."""
    return key.replace("_", " ").title()


def get_template_dir() -> Path:
    """Return the template directory. Falls back to default OneDrive path."""
    return DEFAULT_TEMPLATE_DIR


def list_templates(template_dir: Path | None = None) -> list[TemplateInfo]:
    """Discover available .docx templates and their merge fields."""
    tpl_dir = template_dir or get_template_dir()
    if not tpl_dir.is_dir():
        logger.warning("Template directory not found: %s", tpl_dir)
        return []

    templates = []
    for path in sorted(tpl_dir.glob("*.docx")):
        if path.name.startswith("~$"):
            continue  # skip Word lock files
        try:
            tpl = DocxTemplate(str(path))
            fields = sorted(tpl.get_undeclared_template_variables())
            templates.append(TemplateInfo(
                key=path.stem,
                name=_humanize(path.stem),
                path=path,
                fields=fields,
            ))
        except Exception as e:
            logger.warning("Failed to parse template %s: %s", path.name, e)

    return templates


def get_template(key: str, template_dir: Path | None = None) -> TemplateInfo | None:
    """Look up a single template by key (filename stem)."""
    tpl_dir = template_dir or get_template_dir()
    path = tpl_dir / f"{key}.docx"
    if not path.is_file():
        return None
    try:
        tpl = DocxTemplate(str(path))
        fields = sorted(tpl.get_undeclared_template_variables())
        return TemplateInfo(key=path.stem, name=_humanize(path.stem), path=path, fields=fields)
    except Exception as e:
        logger.warning("Failed to parse template %s: %s", path.name, e)
        return None


# ── Rendering ───────────────────────────────────────────────────


def _version_filename(template_key: str, project_label: str) -> str:
    """Build a versioned filename: TemplateKey_ProjectLabel_v2026-03-20T1430.docx"""
    ts = datetime.now().strftime("%Y-%m-%dT%H%M")
    # Sanitize project label for filename
    safe_label = re.sub(r'[^\w\s-]', '', project_label).strip().replace(' ', '_')
    if safe_label:
        return f"{template_key}_{safe_label}_v{ts}.docx"
    return f"{template_key}_v{ts}.docx"


def _output_dir(template_key: str) -> Path:
    """Return (and create) output directory: data_dir()/documents/<template_key>/"""
    out = data_dir() / "documents" / template_key
    out.mkdir(parents=True, exist_ok=True)
    return out


# OneDrive project folder root
PROJECTS_ROOT = Path(
    r"C:\Users\silen\OneDrive - Ballard Fine Art"
    r"\BALLARD FINE ART - ALL FILES\1. PUBLIC ART\ALL PROJECTS"
)


def find_project_folder(project_name: str) -> Path | None:
    """Find the OneDrive project folder by matching against project name."""
    if not PROJECTS_ROOT.is_dir():
        return None
    target = project_name.lower()
    for folder in PROJECTS_ROOT.iterdir():
        if not folder.is_dir():
            continue
        # Match: folder name contains project name tokens
        fname = folder.name.lower()
        # Split project name into tokens and check all are present
        tokens = target.split()
        if all(t in fname for t in tokens):
            return folder
    return None


def legal_letter_output_dir(project_name: str) -> Path:
    """Return (and create) the legal letters output directory for a project.

    Prefers OneDrive: <project_folder>/Final Documentation/Legal Letters/
    Falls back to: data_dir()/documents/legal_letters/
    """
    project_folder = find_project_folder(project_name)
    if project_folder:
        out = project_folder / "Final Documentation" / "Legal Letters"
        out.mkdir(parents=True, exist_ok=True)
        return out
    out = data_dir() / "documents" / "legal_letters"
    out.mkdir(parents=True, exist_ok=True)
    return out


def render_template(
    template_key: str,
    context: dict[str, str],
    *,
    project_label: str = "",
    template_dir: Path | None = None,
    output_dir: Path | None = None,
) -> RenderResult:
    """
    Render a .docx template with the given context.

    Args:
        template_key: Template filename stem (e.g. "artwork_acceptance")
        context: Merge field values. Keys should match {{field}} names in the template.
        project_label: Used in the output filename for identification.
        template_dir: Override template directory (default: OneDrive _bfa/templates).

    Returns:
        RenderResult with the output path and metadata.
    """
    info = get_template(template_key, template_dir)
    if not info:
        raise FileNotFoundError(f"Template not found: {template_key}")

    # Build versioned filename
    filename = _version_filename(template_key, project_label)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Inject generated_at into context (for footer)
    full_context = {
        **context,
        "generated_at": generated_at,
        "filename": filename,
    }

    # Find unfilled fields
    unfilled = [f for f in info.fields if f not in full_context or not full_context.get(f)]

    # Set unfilled fields to a visible placeholder
    for f in unfilled:
        if f not in full_context:
            full_context[f] = "PENDING"

    tpl = DocxTemplate(str(info.path))
    tpl.render(full_context)

    out = output_dir or _output_dir(template_key)
    output_path = out / filename
    tpl.save(str(output_path))

    logger.info(
        "Rendered %s → %s (%d fields filled, %d unfilled)",
        template_key, filename, len(context), len(unfilled),
    )

    return RenderResult(
        output_path=output_path,
        filename=filename,
        template_key=template_key,
        generated_at=generated_at,
        unfilled=unfilled,
    )


# ── Context Building ───────────────────────────────────────────


def convert_to_pdf(docx_path: Path) -> Path:
    """Convert a .docx file to PDF using Word COM automation. Returns the PDF path."""
    import win32com.client
    import pythoncom

    pythoncom.CoInitialize()
    pdf_path = docx_path.with_suffix(".pdf")
    try:
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        doc = word.Documents.Open(str(docx_path.resolve()))
        doc.SaveAs(str(pdf_path.resolve()), FileFormat=17)  # 17 = wdFormatPDF
        doc.Close()
        word.Quit()
    except Exception as e:
        logger.warning("Word COM issue during PDF conversion: %s", e)
    finally:
        pythoncom.CoUninitialize()

    if not pdf_path.exists():
        raise RuntimeError(f"PDF conversion failed: {pdf_path} not created")
    logger.info("Converted %s to %s", docx_path.name, pdf_path.name)
    return pdf_path


def _title_case_address(addr: str) -> str:
    """Title-case an address, preserving abbreviations and ordinals."""
    import re
    keep_upper = {"bc", "ab", "on", "qc", "ns", "nb", "nw", "ne", "sw", "se", "nwd", "pid"}
    keep_lower = {"and", "of", "the", "at", "in"}
    parts = addr.title().split()
    result = []
    for p in parts:
        low = p.lower().rstrip(".,")
        if low in keep_upper:
            result.append(p.upper())
        elif low in keep_lower and result:  # keep lowercase unless first word
            result.append(p.lower())
        else:
            # Fix ordinals: "34Th" -> "34th"
            result.append(re.sub(r'(\d+)(St|Nd|Rd|Th)\b', lambda m: m.group(1) + m.group(2).lower(), p))
    return " ".join(result)


def _auto_resolve_artist(project_id: str, project_name: str) -> None:
    """Search artist directory for this project and auto-associate if found."""
    import json
    from autohelper.db.conn import get_db
    from autohelper.modules.contacts import hub

    db = get_db()
    # Search manifest JSON for project name in engagement.public_art_projects
    rows = db.execute(
        "SELECT artist_id, manifest_json FROM artists WHERE manifest_json LIKE ?",
        (f"%{project_name}%",),
    ).fetchall()

    for artist_id, manifest_json in rows:
        manifest = json.loads(manifest_json)
        projects = manifest.get("engagement", {}).get("public_art_projects", [])
        for proj in projects:
            if project_name.lower() in (proj.get("project_name") or "").lower():
                # Found a match — extract contact info
                identity = manifest.get("identity", {})
                contact = manifest.get("contact", {})
                display_name = identity.get("display_name", "")
                email = contact.get("email")

                if not display_name:
                    continue

                # Create or find hub contact (requires email)
                hub_contact = None
                if email:
                    hub_contact = hub.get_contact_by_email(email)
                if not hub_contact and email:
                    hub_contact = hub.create_contact(
                        first_name=identity.get("first_name") or display_name.split()[0],
                        last_name=identity.get("last_name") or (display_name.split()[-1] if len(display_name.split()) > 1 else ""),
                        full_name=display_name,
                        email_primary=email,
                        phone_business=contact.get("phone") or "",
                        category="Artist",
                        source="artist_directory",
                    )
                if not hub_contact:
                    # No email — can't create hub contact but still log the match
                    logger.info("Found artist %s for %s but no email — skipping hub", display_name, project_name)

                # Associate with project
                try:
                    hub.associate_contact(
                        contact_id=hub_contact.id,
                        project_id=project_id,
                        role="artist",
                        is_primary=True,
                    )
                except Exception:
                    pass  # Already associated

                logger.info("Auto-resolved artist %s for project %s", display_name, project_name)
                return


def build_project_context(project_id: str) -> dict[str, str]:
    """
    Build a merge context from project intake + contact hub.

    Combines:
    - Project intake fields (project_name, site_address, developer_name, city_name)
    - Contact hub resolved fields (developer_contact_name, artist_email, etc.)
    """
    from autohelper.modules.projects.service import get_project_store
    from autohelper.modules.contacts import hub

    store = get_project_store()
    project = store.get(project_id)
    if not project:
        raise ValueError(f"Project not found: {project_id}")

    intake = project.intake
    context: dict[str, str] = {}

    # From intake
    if intake.project_name:
        context["project_name"] = intake.project_name
        context["development_name"] = intake.project_name
    # Artwork title: from intake, or resolve from project files and persist
    if intake.artwork_title:
        context["artwork_title"] = intake.artwork_title
    else:
        try:
            from .project_files import resolve_project_files
            pf = resolve_project_files(intake.project_name)
            if pf.artwork_title:
                context["artwork_title"] = pf.artwork_title
                # Persist so we don't re-parse next time
                intake.artwork_title = pf.artwork_title
                store.save(project)
                logger.info("Resolved artwork_title=%s from project files", pf.artwork_title)
        except Exception as e:
            logger.warning("Could not resolve artwork title: %s", e)
    if intake.developer_name:
        context["developer_name"] = intake.developer_name
    if intake.neighbourhood:
        context["neighbourhood"] = intake.neighbourhood.title()

    # City overlay — resolve display name from slug
    city_display = ""
    try:
        from autohelper.modules.projects.service import load_city_overlay
        overlay = load_city_overlay(intake.municipality)
        city_display = overlay.city_name
    except Exception:
        if intake.municipality:
            city_display = intake.municipality.replace("-", " ").title()
    if city_display:
        context["city_name"] = city_display

    # Site address from intake — use city display name, not slug
    address_parts = []
    if intake.civic_address:
        address_parts.append(_title_case_address(intake.civic_address))
    if city_display:
        context["site_address"] = ", ".join(address_parts + [city_display.replace("City of ", "")])
    elif address_parts:
        context["site_address"] = ", ".join(address_parts)

    # Auto-resolve artist from artist directory if not already in hub
    try:
        artist_contact = hub.resolve_project_contact(project_id, "artist")
        if not artist_contact:
            _auto_resolve_artist(project_id, intake.project_name)
    except Exception as e:
        logger.warning("Artist auto-resolution failed for %s: %s", project_id, e)

    # Contact hub — resolve per-role contact details
    try:
        hub_fields = hub.resolve_merge_fields(project_id)
        context.update(hub_fields)
    except Exception as e:
        logger.warning("Failed to resolve hub contacts for %s: %s", project_id, e)

    # Per-role detailed contact info (address, phone, etc.)
    for role, prefix in {"developer": "developer", "artist": "artist"}.items():
        try:
            contact = hub.resolve_project_contact(project_id, role)
            if contact:
                # Don't override intake developer_name with hub company
                if f"{prefix}_name" not in context:
                    context[f"{prefix}_name"] = contact.company or contact.full_name
                context[f"{prefix}_contact_name"] = contact.full_name
                context[f"{prefix}_contact_title"] = contact.job_title or ""
                context[f"{prefix}_email"] = contact.email_primary
                context[f"{prefix}_phone"] = contact.phone_business or contact.phone_mobile or ""
                # Address fields
                if contact.street_address:
                    context[f"{prefix}_address_line1"] = contact.street_address
                city_state = ", ".join(filter(None, [contact.city, contact.state]))
                postal = contact.postal_code or ""
                if city_state or postal:
                    context[f"{prefix}_address_line2"] = " ".join(filter(None, [city_state, postal]))
                if contact.country:
                    context[f"{prefix}_country"] = contact.country
        except Exception:
            pass

    # Project-level close-out fields (filled by PM during lifecycle)
    for field in (
        "legal_address", "install_date", "agreement_date", "agreement_section",
        "declarant_name", "declarant_title", "declarant_address",
        "declaration_city", "declaration_date",
        "final_report_author", "registration_type", "registration_number",
    ):
        val = getattr(project, field, None)
        if val:
            context[field] = val

    return context
