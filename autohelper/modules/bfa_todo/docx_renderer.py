"""
Render the BFA To Do List as a .docx file matching the existing format.

Produces a Word document with:
- Preamble (PAC meetings, city contacts, rates)
- Proposals & Programs lists
- Project blocks with formatting matching the legacy doc
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

from autohelper.shared.paths import data_dir

logger = logging.getLogger(__name__)


def render_todo_docx(
    projects: list[dict],
    output_path: Path | None = None,
) -> Path:
    """Render the full BFA To Do list as a .docx file.

    Args:
        projects: All project/preamble dicts from the repo.
        output_path: Where to save. Defaults to data_dir()/bfa_todo/site/todo_list.docx

    Returns:
        Path to the generated .docx file.
    """
    doc = Document()

    # Set default font
    style = doc.styles["Normal"]
    style.font.name = "Arial"
    style.font.size = Pt(11)

    # Separate preambles from projects
    preambles = [p for p in projects if p.get("type") in ("preamble", "preamble-lists")]
    project_list = [p for p in projects if p.get("type") == "project" and p.get("status") != "archived"]

    # Sort preambles: main preamble first, then lists
    preambles.sort(key=lambda p: 0 if p["type"] == "preamble" else 1)

    # Render preambles
    for preamble in preambles:
        _render_preamble(doc, preamble)

    # Render projects
    for project in project_list:
        _render_project(doc, project)

    # Save
    if output_path is None:
        out_dir = data_dir() / "bfa_todo" / "site"
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / "todo_list.docx"

    doc.save(str(output_path))
    logger.info("Rendered To Do list: %d projects -> %s", len(project_list), output_path)
    return output_path


def _render_preamble(doc: Document, preamble: dict) -> None:
    """Render a preamble block — preserves the text with basic formatting."""
    content = preamble.get("sections", {}).get("content", {})
    text = content.get("text", "")
    if not text.strip():
        return

    # Update the heading date for the main preamble
    if preamble["type"] == "preamble":
        import re
        today = datetime.now()
        date_str = f"{today.strftime('%B')} {today.day}, {today.year}"
        text = re.sub(
            r"To Do List\s+\w+ \d{1,2},?\s*\d{4}",
            f"To Do List {date_str}",
            text,
        )

    lines = text.split("\n")
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        para = doc.add_paragraph()
        run = para.add_run(line)

        # First line of main preamble is the title
        if i == 0 and preamble["type"] == "preamble":
            run.bold = True
            run.font.size = Pt(11)
        # City headers (e.g., "Vancouver:", "Burnaby:") are bold+underline
        elif ":" in line and len(line) < 80 and any(
            city in line.lower()
            for city in ["vancouver", "burnaby", "richmond", "north van", "surrey",
                         "coquitlam", "port moody", "white rock", "saanich", "squamish"]
        ):
            run.bold = True
            run.underline = True
            run.font.size = Pt(8)
        # Contact lines and policy detail at 8pt
        elif line.startswith("Contact:") or line.startswith("rate:") or line.startswith("$"):
            run.font.size = Pt(8)
        # Section headers in the proposals list
        elif preamble["type"] == "preamble-lists" and not line.startswith("("):
            # Category headers like "Proposals (New Projects)", "Longlists", etc.
            if any(line.startswith(h) for h in [
                "Proposals", "Art Plans", "Longlists", "Final Documents",
                "Artist Contracts", "MASTER", "Delays",
            ]):
                run.bold = True
                run.underline = True
        else:
            run.font.size = Pt(8)

    # Add a blank line after each preamble
    doc.add_paragraph()


def _render_project(doc: Document, project: dict) -> None:
    """Render a single project block matching the legacy format."""
    fields = project.get("fields", {})
    sections = project.get("sections", {})

    client = fields.get("client", "TBC")
    project_name = fields.get("project_name", "TBC")
    city = fields.get("city", "TBC")
    owner_team = fields.get("owner_team", "BFA")
    phase = project.get("bfa_phase_canonical", "")

    # Header line: (PM) Client - Project, City (Budget) \tInstall: Date
    header_text = project.get("header", {}).get("text", "")
    if not header_text:
        header_text = f"({owner_team}) {project_name}, {city}"

    para = doc.add_paragraph()
    run = para.add_run(header_text)
    run.bold = True
    run.underline = True
    run.font.size = Pt(11)

    # Contacts line
    contacts = fields.get("contacts_text", "")
    if contacts:
        p = doc.add_paragraph()
        r = p.add_run(contacts)
        r.font.size = Pt(11)

    # Artists
    artists = fields.get("artists_text", "")
    if artists:
        p = doc.add_paragraph()
        r = p.add_run(artists)
        r.font.size = Pt(11)

    # Sections: content, next_steps, milestones, etc.
    for sec_name in ("content", "milestones", "next_steps", "governance", "fabrication"):
        sec = sections.get(sec_name, {})
        text = sec.get("text", "").strip()
        if not text:
            continue
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            p = doc.add_paragraph()
            r = p.add_run(line)
            r.bold = sec_name in ("milestones", "next_steps")
            r.font.size = Pt(11)

    # Project status
    if phase:
        p = doc.add_paragraph()
        r = p.add_run(f"Project Status: {phase}")
        r.bold = True
        r.font.size = Pt(11)

    # Blank line between projects
    doc.add_paragraph()
