"""
Bidirectional adapter: .docx <-> DB dict <-> ClickUp.

Owns the field mapping in both directions so the BFA To Do list can
round-trip through Word edits without data loss.

    docx_to_projects(path)  -- parse .docx back to project dicts (via SDTs)
    diff_projects(parsed, db) -- field + section level diff
    project_to_clickup(entry, record) -- map to ClickUp update payload
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# .docx -> project dicts (SDT-based extraction)
# ---------------------------------------------------------------------------

def docx_to_projects(docx_path: str | Path) -> list[dict[str, Any]]:
    """Parse a BFA To Do .docx into project dicts via SDT content controls.

    Each project block is wrapped in a w:sdt with tag "bfa:project:uid=..."
    and sections within are wrapped with "bfa:section:..." tags.
    These SDTs are embedded at generation time by docx_renderer.py.

    Returns dicts shaped like the DB schema:
        {uid, fields, header: {text}, sections: {name: {text}}}
    """
    from docx import Document
    from docx.oxml.ns import qn
    from .pipeline.importer import _parse_header_fields

    doc = Document(str(docx_path))
    body = doc.element.body

    projects: list[dict[str, Any]] = []

    for sdt in body.findall(qn("w:sdt")):
        sdt_pr = sdt.find(qn("w:sdtPr"))
        if sdt_pr is None:
            continue
        tag_el = sdt_pr.find(qn("w:tag"))
        if tag_el is None:
            continue
        tag_val = tag_el.get(qn("w:val"), "")
        if not tag_val.startswith("bfa:project:"):
            continue

        # Extract UID from tag
        uid = tag_val.split("uid=", 1)[1] if "uid=" in tag_val else ""

        # Alias = header text fallback
        alias_el = sdt_pr.find(qn("w:alias"))
        alias_text = alias_el.get(qn("w:val"), "") if alias_el is not None else ""

        content = sdt.find(qn("w:sdtContent"))
        if content is None:
            continue

        # Walk direct children: first w:p is header, w:sdt children are
        # sections, remaining w:p children are unmapped notes.
        header_text = alias_text
        sections: dict[str, dict[str, str]] = {}
        unmapped_lines: list[str] = []
        first_para_seen = False

        for child in content:
            if child.tag == qn("w:p"):
                if not first_para_seen:
                    first_para_seen = True
                    para_text = _sdt_para_text(child)
                    if para_text:
                        header_text = para_text
                else:
                    text = _sdt_para_text(child)
                    if text:
                        unmapped_lines.append(text)

            elif child.tag == qn("w:sdt"):
                # Section-level SDT
                inner_pr = child.find(qn("w:sdtPr"))
                if inner_pr is None:
                    continue
                inner_tag = inner_pr.find(qn("w:tag"))
                if inner_tag is None:
                    continue
                inner_val = inner_tag.get(qn("w:val"), "")
                if not inner_val.startswith("bfa:section:"):
                    continue

                sec_name = inner_val[len("bfa:section:"):]
                inner_content = child.find(qn("w:sdtContent"))
                if inner_content is None:
                    continue

                sec_text = _sdt_content_text(inner_content)
                if sec_name in sections:
                    sections[sec_name]["text"] += "\n" + sec_text
                else:
                    sections[sec_name] = {"text": sec_text}

        if unmapped_lines:
            unmapped_text = "\n".join(unmapped_lines)
            if "unmapped" in sections:
                sections["unmapped"]["text"] += "\n" + unmapped_text
            else:
                sections["unmapped"] = {"text": unmapped_text}

        fields = _parse_header_fields(header_text)

        projects.append({
            "uid": uid,
            "fields": fields,
            "header": {"text": header_text},
            "sections": sections,
        })

    if not projects:
        logger.warning("No SDT-tagged projects found in %s", Path(docx_path).name)
    else:
        logger.info(
            "Parsed %d SDT-tagged projects from %s",
            len(projects), Path(docx_path).name,
        )

    return projects


def _sdt_para_text(para_el) -> str:
    """Get text from a paragraph element by joining w:t texts."""
    from docx.oxml.ns import qn

    texts = []
    for t in para_el.iter(qn("w:t")):
        if t.text:
            texts.append(t.text)
    return "".join(texts).strip()


def _sdt_content_text(content_el) -> str:
    """Get all text from an sdtContent element, joining paragraphs."""
    from docx.oxml.ns import qn

    lines = []
    for p in content_el.findall(qn("w:p")):
        lines.append(_sdt_para_text(p))
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Diff: parsed .docx vs DB entries
# ---------------------------------------------------------------------------

@dataclass
class Delta:
    """A single field or section change."""
    uid: str
    header_text: str
    category: str  # "field" or "section"
    name: str      # field name or section name
    old: str
    new: str


def diff_projects(
    parsed: list[dict[str, Any]],
    db_entries: list[dict[str, Any]],
) -> list[Delta]:
    """Compare parsed .docx projects against DB entries.

    Matches by UID (from SDT tags) first, then falls back to header
    text similarity.  Returns a list of Deltas for differences.
    """
    deltas: list[Delta] = []
    db_by_uid = {
        e.get("uid", ""): e
        for e in db_entries
        if e.get("type") == "project"
    }

    for docx_proj in parsed:
        docx_uid = docx_proj.get("uid", "")
        docx_header = docx_proj["header"]["text"]

        # Match by UID first (deterministic), fall back to header text
        db_entry = db_by_uid.get(docx_uid) if docx_uid else None
        if db_entry is None:
            db_entry = _match_db_entry(docx_header, db_entries)
        if db_entry is None:
            logger.debug("No DB match for: %s (uid=%s)", docx_header[:80], docx_uid)
            continue

        uid = db_entry.get("uid", docx_uid)
        db_fields = db_entry.get("fields", {})
        docx_fields = docx_proj.get("fields", {})

        # Compare fields
        for key in set(docx_fields) | set(db_fields):
            old = db_fields.get(key, "")
            new = docx_fields.get(key, "")
            if _normalize_for_diff(old) != _normalize_for_diff(new):
                deltas.append(Delta(
                    uid=uid, header_text=docx_header,
                    category="field", name=key, old=str(old), new=str(new),
                ))

        # Compare section text
        db_sections = db_entry.get("sections", {})
        docx_sections = docx_proj.get("sections", {})
        for sec_name in set(docx_sections) | set(db_sections):
            old = db_sections.get(sec_name, {}).get("text", "")
            new = docx_sections.get(sec_name, {}).get("text", "")
            if _normalize_for_diff(old) != _normalize_for_diff(new):
                deltas.append(Delta(
                    uid=uid, header_text=docx_header,
                    category="section", name=sec_name, old=old, new=new,
                ))

    logger.info("Diff: %d deltas across %d parsed projects", len(deltas), len(parsed))
    return deltas


def _match_db_entry(
    header_text: str, db_entries: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Match a parsed header to a DB entry by text similarity (fallback)."""
    header_lower = header_text.lower()

    for entry in db_entries:
        if entry.get("type") != "project":
            continue
        db_header = entry.get("header", {}).get("text", "").lower()
        # Exact or substring match
        if header_lower == db_header:
            return entry
        if header_lower in db_header or db_header in header_lower:
            return entry
        # Match on client + project_name
        fields = entry.get("fields", {})
        client = fields.get("client", "").lower()
        proj = fields.get("project_name", "").lower()
        if client and proj and client in header_lower and proj in header_lower:
            return entry

    return None


# Compiled once: label prefixes that may appear in .docx but not in DB.
# Used by _normalize_for_diff to strip them before comparison.
_DIFF_LABEL_PREFIX_RE = re.compile(
    r"^(?:Contact|Owner|Architect|Landscape|PPAP|DPAP|EOI|SP#[12]|AO|"
    r"Selection Panel|Community Advisor[sy]?|Shortlisted Artists|Selected Artist|"
    r"Artwork Title|Project Status|BFA Project Status|Next Steps|BFA Next Steps|"
    r"Fabricat(?:or|ors?|ion)\s*(?:\d+%)?|"
    r"(?:\d+%\s*)?Fabrication|"
    r"Review of art before delivery|Checklist|NVPAAC Rep|"
    r"Installation|Storage|Final Report)\s*:?\s*",
    re.IGNORECASE | re.MULTILINE,
)

# Unicode replacements: smart quotes, em/en dashes, ellipsis, etc.
_UNICODE_MAP = str.maketrans({
    "\u2018": "'",   # left single curly quote
    "\u2019": "'",   # right single curly quote / apostrophe
    "\u201C": '"',   # left double curly quote
    "\u201D": '"',   # right double curly quote
    "\u2013": "-",   # en dash
    "\u2014": "-",   # em dash
    "\u2026": "...", # ellipsis
    "\u00A0": " ",   # non-breaking space
    "\u200B": "",    # zero-width space
    "\u00AD": "",    # soft hyphen
    "\uFEFF": "",    # BOM / zero-width no-break space
})


def _normalize_for_diff(val: str) -> str:
    """Normalize a value for comparison.

    Steps:
    1. Replace non-breaking spaces, smart quotes, em dashes, etc.
    2. NFC-normalize unicode.
    3. Strip label prefixes BEFORE collapsing whitespace (needs line starts).
    4. Strip decorative characters (box drawing, horizontal rules).
    5. Collapse all whitespace to single space.
    6. Lowercase + strip.
    """
    if not val:
        return ""
    s = val.translate(_UNICODE_MAP)
    s = unicodedata.normalize("NFC", s)
    # Strip label prefixes while newlines still exist (regex uses ^ MULTILINE)
    s = _DIFF_LABEL_PREFIX_RE.sub("", s)
    # Strip decorative line characters (ON HOLD separator, horizontal rules)
    s = re.sub(r"[─━═─\u2500-\u257F]+", "", s)
    # Collapse all whitespace to single space
    s = re.sub(r"[\s\xa0]+", " ", s).strip()
    return s.strip()


# ---------------------------------------------------------------------------
# DB dict -> ClickUp update
# ---------------------------------------------------------------------------

def project_to_clickup_updates(
    entry: dict[str, Any],
    project_record: Any,
) -> dict[str, Any]:
    """Map a BFA entry to ClickUp update payloads.

    Returns:
        {
            "task_update": UpdateTaskData dict (name, description),
            "custom_fields": [{field_id, value}, ...],
            "comment": str | None,
        }
    """
    fields = entry.get("fields", {})
    sections = entry.get("sections", {})

    # Task name: "Client - Project Name"
    client = fields.get("client", "")
    proj_name = fields.get("project_name", "")
    task_name = f"{client} - {proj_name}" if client and proj_name else proj_name or client

    # Description: contacts + artists + phase + next steps
    desc_parts = []
    for sec_name in ("contacts", "artists", "artwork_title", "bfa_phase", "next_steps"):
        sec = sections.get(sec_name, {})
        text = sec.get("text", "").strip()
        if text:
            desc_parts.append(text)
    description = "\n\n".join(desc_parts)

    # Custom fields: map BFA fields to ClickUp field IDs
    # The field IDs are project-specific (stored on ProjectRecord)
    custom_fields = []
    # These will be resolved by the caller using project_record.clickup_stage_field_id etc.

    # Notes as comment
    unmapped = sections.get("unmapped", {}).get("text", "")
    comment = unmapped if unmapped.strip() else None

    return {
        "task_name": task_name,
        "description": description,
        "custom_fields": custom_fields,
        "comment": comment,
        "fields": {
            "install_date": fields.get("install_date", ""),
            "city": fields.get("city", ""),
            "art_budget": fields.get("art_budget", ""),
            "total_budget": fields.get("total_budget", ""),
            "phase": sections.get("bfa_phase", {}).get("text", ""),
        },
    }
