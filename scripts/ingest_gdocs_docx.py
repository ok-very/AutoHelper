"""Ingest source 1 (gdocs docx) into the BFA Todo DB.

Parses projects from paragraph structure, matches against DB,
applies section/header updates, creates new entries for unmatched.
"""
import html as html_mod
import re
import uuid

from docx import Document

from autohelper.config import get_settings
from autohelper.db import init_db
from autohelper.db.migrate import run_migrations

settings = get_settings()
db = init_db(settings.db_path)
run_migrations(db)

from autohelper.modules.bfa_todo.pipeline.repo import BfaProjectRepo
from autohelper.modules.bfa_todo.pipeline.importer import _parse_header_fields

repo = BfaProjectRepo()

DOCX_PATH = r"C:\Users\Neal\Downloads\2026_01_08_Ballard Fine Art To Do - gdocs.docx"

# Section label detection — longest match first
SECTION_LABELS = {
    "bfa project status": "bfa_phase",
    "bfa next step": "next_steps",
    "project status": "bfa_phase",
    "community advisory": "contacts",
    "selection panel": "contacts",
    "artwork title": "artwork_title",
    "selected artist": "artists",
    "shortlisted": "artists",
    "next steps": "next_steps",
    "next step": "next_steps",
    "bfa phase": "bfa_phase",
    "review of art": "fabrication",
    "final report": "fabrication",
    "installation": "fabrication",
    "milestone": "milestones",
    "governance": "governance",
    "fabricat": "fabrication",
    "landscape": "contacts",
    "architect": "contacts",
    "contacts": "contacts",
    "contact": "contacts",
    "storage": "fabrication",
    "artists": "artists",
    "artist": "artists",
    "nvpaac": "contacts",
    "owner": "contacts",
    "phase": "bfa_phase",
    "ppap": "contacts",
    "dpap": "contacts",
    "team": "contacts",
    "sp#1": "contacts",
    "sp#2": "contacts",
    "eoi": "contacts",
    "ao": "contacts",
}


def detect_section(text):
    t = text.lower().strip()
    for label, sec in SECTION_LABELS.items():
        if t.startswith(label):
            return sec
    return None


def is_header_para(p):
    text = p.text.strip()
    if not text:
        return False
    if p.style and p.style.name == "Heading 3":
        return True
    if text.startswith("(") and len(text) > 30:
        if any(kw in text for kw in ["Artwork", "Total", "Install", "Art:", "ON HOLD"]):
            return True
    return False


def text_to_html(text):
    lines = []
    for line in text.split("\n"):
        if line.strip():
            lines.append(f"<p>{html_mod.escape(line)}</p>")
    return "\n".join(lines)


# --- Parse docx ---
doc = Document(DOCX_PATH)

docx_projects = []
current = None
preamble_done = False

for p in doc.paragraphs:
    text = p.text.strip()
    if is_header_para(p):
        preamble_done = True
        if current:
            docx_projects.append(current)
        current = {"header": text, "sections": {}, "_cur": "contacts"}
    elif preamble_done and current is not None and text:
        sec = detect_section(text)
        if sec:
            current["_cur"] = sec
        current["sections"].setdefault(current["_cur"], []).append(text)

if current:
    docx_projects.append(current)

for proj in docx_projects:
    del proj["_cur"]
    for k, lines in proj["sections"].items():
        proj["sections"][k] = "\n".join(lines)

print(f"Parsed {len(docx_projects)} projects from docx")

# --- Load DB ---
db_entries = repo.get_all(include_archived=False)
db_projects = [e for e in db_entries if e.get("type") == "project"]

# Build lookup index
db_by_header = {}
for e in db_projects:
    h = re.sub(r"[\s\xa0]+", " ", (e.get("header", {}).get("text", "")).lower().strip())
    db_by_header[h] = e


def find_match(header):
    h = re.sub(r"[\s\xa0]+", " ", header.lower().strip())
    if h in db_by_header:
        return db_by_header[h]
    for db_h, e in db_by_header.items():
        if len(h) > 20 and (h[:40] in db_h or db_h[:40] in h):
            return e
    for e in db_projects:
        f = e.get("fields", {})
        cl = f.get("client", "").lower()
        pn = f.get("project_name", "").lower()
        if cl and pn and len(cl) > 2 and len(pn) > 2 and cl in h and pn in h:
            return e
    return None


# --- Match + apply ---
updated = 0
created = 0
skipped = 0

for proj in docx_projects:
    header = proj["header"]

    if header.strip().lower().startswith("project cancel"):
        skipped += 1
        continue

    db_match = find_match(header)

    if db_match:
        entry = db_match.copy()
        entry["header"] = {
            "text": header,
            "html": f'<h3><span style="font-weight:700;text-decoration:underline;font-size:11pt">'
                    f"{html_mod.escape(header)}</span></h3>",
        }

        # Update fields from header parse
        try:
            parsed_fields = _parse_header_fields(header)
            if parsed_fields:
                for k, v in parsed_fields.items():
                    if v and v != "TBC":
                        entry["fields"][k] = v
        except Exception:
            pass

        # Update sections
        for sec_name, text in proj["sections"].items():
            entry["sections"][sec_name] = {
                "text": text,
                "html": text_to_html(text),
            }

        # Remove sections that were emptied (milestones, unmapped absorbed)
        for sec_name in list(entry["sections"].keys()):
            if sec_name not in proj["sections"]:
                # Keep sections the docx doesn't mention — they may have been
                # generated by other sources (ClickUp sync etc.)
                pass

        # Extract phase display from bfa_phase section
        bfa_text = proj["sections"].get("bfa_phase", "")
        if bfa_text:
            phase_line = bfa_text.split("\n")[0]
            phase_line = re.sub(
                r"^(?:Project Status|BFA (?:Project )?Status)\s*:?\s*",
                "", phase_line, flags=re.IGNORECASE,
            ).strip()
            if phase_line:
                entry["bfa_phase_display"] = phase_line

        repo.upsert(entry, allow_curated=True)
        updated += 1
    else:
        # New project
        fields = {}
        try:
            fields = _parse_header_fields(header) or {}
        except Exception:
            pass

        fingerprint = (
            f"{fields.get('client', '?')}|"
            f"{fields.get('project_name', '?')}|"
            f"{fields.get('city', '?')}"
        )
        uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, fingerprint))
        slug_raw = (
            f"bfa-{fields.get('client', '')}-"
            f"{fields.get('project_name', '')}-"
            f"{fields.get('city', '')}"
        )
        slug = re.sub(r"[^a-z0-9]+", "-", slug_raw.lower()).strip("-")[:50]
        slug = f"{slug}-{uid[:8]}"

        sections = {}
        for sec_name, text in proj["sections"].items():
            sections[sec_name] = {"text": text, "html": text_to_html(text)}

        phase_display = "TBC"
        bfa_text = proj["sections"].get("bfa_phase", "")
        if bfa_text:
            phase_line = bfa_text.split("\n")[0]
            phase_line = re.sub(
                r"^(?:Project Status|BFA (?:Project )?Status)\s*:?\s*",
                "", phase_line, flags=re.IGNORECASE,
            ).strip()
            if phase_line:
                phase_display = phase_line

        # Detect ON HOLD from header
        status = "active"
        if "ON HOLD" in header.upper():
            status = "on_hold"

        entry = {
            "uid": uid,
            "slug": slug,
            "fingerprint": fingerprint,
            "type": "project",
            "status": status,
            "source": "gdocs",
            "fields": fields,
            "header": {
                "text": header,
                "html": f'<h3><span style="font-weight:700;text-decoration:underline;font-size:11pt">'
                        f"{html_mod.escape(header)}</span></h3>",
            },
            "sections": sections,
            "bfa_phase_display": phase_display,
            "bfa_phase_canonical": "TBC",
            "next_steps": [],
        }

        repo.upsert(entry, allow_curated=True)
        created += 1
        print(f"  NEW: {header[:80]}")

print(f"\nDone: {updated} updated, {created} created, {skipped} skipped")
