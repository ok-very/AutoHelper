"""
Bidirectional adapter: .docx ↔ DB dict ↔ ClickUp.

Owns the field mapping in both directions so the BFA To Do list can
round-trip through Word edits without data loss.

    docx_to_projects(path)  — parse .docx back to project dicts
    diff_projects(parsed, db) — field + section level diff
    project_to_clickup(entry, record) — map to ClickUp update payload
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
# .docx → project dicts
# ---------------------------------------------------------------------------

def docx_to_projects(docx_path: str | Path) -> list[dict[str, Any]]:
    """Parse a BFA To Do .docx into a list of project dicts.

    Returns dicts shaped like the DB schema:
        {fields, header: {text}, sections: {name: {text}}}

    Reuses _parse_header_fields from the HTML importer for header extraction
    and SECTION_LABELS / CONTACT_RELATED_SECTIONS for body classification.
    """
    from docx import Document

    from .pipeline.importer import (
        CONTACT_RELATED_SECTIONS,
        _parse_header_fields,
    )
    from .pipeline.config import SECTION_LABELS

    doc = Document(str(docx_path))
    paras = doc.paragraphs

    # -- Phase 1: Split paragraphs into project blocks --
    blocks: list[dict[str, Any]] = []
    current_header_idx: int | None = None

    for i, p in enumerate(paras):
        text = (p.text or "").strip()
        style = p.style.name if p.style else ""

        if _is_project_header(text, style):
            if current_header_idx is not None:
                blocks.append(_collect_block(paras, current_header_idx, i))
            current_header_idx = i

    # Last block
    if current_header_idx is not None:
        blocks.append(_collect_block(paras, current_header_idx, len(paras)))

    logger.info("Parsed %d project blocks from %s", len(blocks), Path(docx_path).name)

    # -- Phase 2: Extract fields + sections from each block --
    projects: list[dict[str, Any]] = []

    for block in blocks:
        header_text = block["header_text"]
        fields = _parse_header_fields(header_text)

        sections = _classify_docx_sections(
            block["body_paras"], SECTION_LABELS, CONTACT_RELATED_SECTIONS,
        )

        projects.append({
            "fields": fields,
            "header": {"text": header_text},
            "sections": sections,
        })

    return projects


def _is_project_header(text: str, style_name: str) -> bool:
    """Detect a project header paragraph."""
    if not text.startswith("("):
        return False
    if ":" not in text:
        return False
    # Must have budget or install info, OR be Heading 3 style
    has_keywords = any(kw in text for kw in ("Artwork", "Total", "Install"))
    is_heading = "Heading" in style_name
    return has_keywords or (is_heading and len(text) > 30)


def _collect_block(
    paras: list, start: int, end: int,
) -> dict[str, Any]:
    """Collect a project block from start (header) to end (next header)."""
    header_text = (paras[start].text or "").strip()

    # Body paragraphs: everything after header, skip trailing blanks
    body = []
    for i in range(start + 1, end):
        text = (paras[i].text or "").strip()
        runs_info = _extract_runs(paras[i])
        body.append({"text": text, "runs": runs_info, "index": i})

    # Trim trailing blanks
    while body and not body[-1]["text"]:
        body.pop()

    return {"header_text": header_text, "body_paras": body}


def _extract_runs(para) -> list[dict[str, Any]]:
    """Extract run-level info (text + bold) from a paragraph."""
    runs = []
    for r in para.runs:
        runs.append({
            "text": r.text,
            "bold": r.font.bold is True,
        })
    return runs


def _classify_docx_sections(
    body_paras: list[dict],
    section_labels: dict[str, str],
    contact_related: set[str],
) -> dict[str, dict[str, str]]:
    """Classify body paragraphs into named sections by bold label detection.

    Mirrors pipeline/importer.py:_classify_sections but works on
    extracted paragraph dicts instead of lxml elements.
    """
    sections: dict[str, dict[str, str]] = {}
    current_section: str | None = None
    current_text: list[str] = []

    def _flush():
        nonlocal current_section, current_text
        if current_section and current_text:
            store_as = current_section
            if store_as in contact_related:
                store_as = "contacts"
            text = "\n".join(current_text)
            if store_as in sections:
                sections[store_as]["text"] += "\n" + text
            else:
                sections[store_as] = {"text": text}
        elif current_text:
            text = "\n".join(current_text)
            if "unmapped" not in sections:
                sections["unmapped"] = {"text": ""}
            sections["unmapped"]["text"] += "\n" + text
        current_text = []

    for para in body_paras:
        text = para["text"]
        if not text:
            continue

        # Detect section label from bold prefix ONLY.
        # Text-based fallback is too greedy (e.g. "Artist 'Kick off'..." matches
        # "artist" → artists section). The original HTML importer also uses bold
        # detection as the primary mechanism.
        label = _detect_label_from_runs(para["runs"], section_labels)

        if label:
            _flush()
            current_section = label

        current_text.append(text)

    _flush()

    # Clean up
    for sec in sections.values():
        sec["text"] = sec["text"].strip()

    # Strip leading label prefixes from section text.
    # DB stores "Duncan Wade, ..." but .docx has "Contact: Duncan Wade, ..."
    # Normalize so diffs don't flag every section as changed.
    _LABEL_PREFIX_RE = re.compile(
        r"^(?:Contact|Owner|Architect|Landscape|PPAP|DPAP|EOI|SP#[12]|AO|"
        r"Selection Panel|Community Advisor[sy]?|Shortlisted Artists|Selected Artist|"
        r"Artwork Title|Project Status|BFA Project Status|Next Steps|BFA Next Steps|"
        r"Fabricat(?:or|ors?|ion)\s*(?:\d+%)?|"
        r"(?:\d+%\s*)?Fabrication|"
        r"Review of art before delivery|Checklist|NVPAAC Rep|"
        r"Installation|Storage|Final Report)\s*:?\s*",
        re.IGNORECASE | re.MULTILINE,
    )
    for sec in sections.values():
        sec["text"] = _LABEL_PREFIX_RE.sub("", sec["text"]).strip()

    return sections


def _detect_label_from_runs(
    runs: list[dict], section_labels: dict[str, str],
) -> str | None:
    """Detect a section label from the first bold run."""
    if not runs:
        return None
    first = runs[0]
    if not first["bold"]:
        return None
    label_text = first["text"].lower().rstrip(":").strip()
    return section_labels.get(label_text)


def _detect_label_from_text(
    text: str, section_labels: dict[str, str],
) -> str | None:
    """Detect a section label from the paragraph text prefix."""
    clean = text.lower().rstrip(":").strip()
    # Check exact match
    if clean in section_labels:
        return section_labels[clean]
    # Check prefix match
    sorted_keys = sorted(section_labels.keys(), key=len, reverse=True)
    for key in sorted_keys:
        if clean.startswith(key):
            after = clean[len(key):]
            if after and after[0] in (":", " ", "\t"):
                return section_labels[key]
    return None


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

    Matches by header text similarity.  Returns a list of Deltas
    for fields and sections that differ.
    """
    deltas: list[Delta] = []

    for docx_proj in parsed:
        docx_header = docx_proj["header"]["text"]
        db_entry = _match_db_entry(docx_header, db_entries)
        if db_entry is None:
            logger.debug("No DB match for: %s", docx_header[:80])
            continue

        uid = db_entry.get("uid", "")
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
    """Match a parsed header to a DB entry by text similarity."""
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
# DB dict → ClickUp update
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
