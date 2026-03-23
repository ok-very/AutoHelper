"""
Pass 2: Render project modules into a single HTML document.

Uses stored HTML fragments + canonical CSS (pruned Google Docs + base overrides).
Wraps each project in uniform anchor-tagged sections.
"""

import html as html_mod
import re
import shutil
from jinja2 import Environment, FileSystemLoader
from . import config
from .style_resolver import StyleResolver, walk_html_for_runs, runs_to_inline_html
from .gdocs_export import generate_gdocs_json


# Known label prefixes that should render bold (PM format).
# Sorted longest-first for greedy matching.
_BOLD_LABELS = sorted([
    "Community Advisory", "Selection Panel", "Shortlisted Artists",
    "Selected Artist", "Fabrication 100%", "Fabrication 75%",
    "Fabrication 50%", "Fabrication 25%", "Project Status",
    "Artwork Title", "Final Report", "Installation", "Next Steps",
    "Next Step", "Fabrication", "Landscape", "Architect", "Contact",
    "NVPAAC Rep", "Storage", "Owner", "PPAP", "DPAP", "SP#1",
    "SP#2", "EOI", "AO", "PM",
], key=lambda x: -len(x))


def _render_section_html(text: str) -> str:
    """Render section text to HTML with bold label prefixes.

    Matches PM format: each line with a recognized label prefix gets
    the label portion wrapped in <b>. Lines are wrapped in <p> with
    11pt Calibri inline style. Empty lines become blank <p> for spacing.
    """
    p_style = (
        'style="margin:0;font-size:11pt;font-family:Calibri,sans-serif;'
        'line-height:1.15;color:#000"'
    )

    parts = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            parts.append(f"<p {p_style}>&nbsp;</p>")
            continue

        # Check for a known label prefix
        rendered = False
        for label in _BOLD_LABELS:
            if stripped.startswith(label + ":") or stripped.startswith(label + " :"):
                colon_pos = stripped.index(":")
                label_part = html_mod.escape(stripped[:colon_pos + 1])
                value_part = html_mod.escape(stripped[colon_pos + 1:])
                parts.append(
                    f"<p {p_style}><b>{label_part}</b>{value_part}</p>"
                )
                rendered = True
                break

        if not rendered:
            parts.append(f"<p {p_style}>{html_mod.escape(stripped)}</p>")

    return "\n".join(parts)


def _load_templates():
    env = Environment(
        loader=FileSystemLoader(str(config.TEMPLATE_DIR)),
        autoescape=False,
    )
    page_tpl = env.get_template("page.html.j2")
    project_tpl = env.get_template("project.html.j2")
    preamble_tpl = env.get_template("preamble.html.j2")
    preamble_lists_tpl = env.get_template("preamble_lists.html.j2")
    return page_tpl, project_tpl, preamble_tpl, preamble_lists_tpl


def render_project(project_data, project_tpl, preamble_tpl, preamble_lists_tpl):
    if project_data["type"] == "preamble-lists":
        return preamble_lists_tpl.render(p=project_data)
    if project_data["type"] == "preamble":
        return preamble_tpl.render(p=project_data)
    return project_tpl.render(p=project_data)


def _build_canonical_css(gdocs_css):
    """Prune gdocs CSS to only rules referenced in the output, merge with base overrides."""
    base_css_path = config.TEMPLATE_DIR / "base.css"
    base_css = ""
    if base_css_path.exists():
        base_css = base_css_path.read_text(encoding="utf-8")

    if not gdocs_css:
        return base_css

    # Parse gdocs CSS into rule blocks
    blocks = []
    depth = 0
    current = []
    for char in gdocs_css:
        current.append(char)
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth <= 0:
                block = ''.join(current).strip()
                if block:
                    blocks.append(block)
                current = []
                depth = 0

    return blocks, base_css


def _prune_gdocs_rules(blocks, used_classes, base_css):
    """Keep only gdocs rules that reference classes found in the rendered HTML."""
    element_rules = []
    class_rules = []
    list_rules = []

    for block in blocks:
        brace = block.find('{')
        if brace == -1:
            continue
        selector = block[:brace].strip()
        class_refs = set(re.findall(r'\.([\w-]+)', selector))

        if not class_refs:
            element_rules.append(block)
        elif class_refs & used_classes:
            if any(c.startswith('lst-') for c in class_refs):
                list_rules.append(block)
            else:
                class_rules.append(block)

    parts = []
    parts.append("/* ═══════════════════════════════════════════════════════")
    parts.append("   BFA To Do List — Canonical Stylesheet")
    parts.append("   Pruned from Google Docs export + base overrides")
    parts.append("   ═══════════════════════════════════════════════════════ */")
    parts.append("")
    parts.append("/* ── Global resets (from Google Docs) ── */")
    parts.extend(element_rules)
    parts.append("")
    parts.append("/* ── Google Docs class definitions ── */")
    parts.extend(class_rules)
    parts.append("")
    parts.append("/* ── List counter styles ── */")
    parts.extend(list_rules)
    parts.append("")
    parts.append("/* ═══════════════════════════════════════════════════════")
    parts.append("   BFA Overrides — layout, project cards, semantic styles")
    parts.append("   ═══════════════════════════════════════════════════════ */")
    parts.append("")
    parts.append(base_css)

    return '\n'.join(parts)


def render_site(processed_projects, gdocs_css):
    config.SITE_DIR.mkdir(parents=True, exist_ok=True)
    config.ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    # Save raw gdocs CSS for reference
    raw_css_path = config.ASSETS_DIR / "gdocs.css"
    raw_css_path.write_text(gdocs_css, encoding="utf-8")

    # Parse gdocs rules + load base overrides
    parsed = _build_canonical_css(gdocs_css)
    if isinstance(parsed, tuple):
        gdocs_blocks, base_css = parsed
    else:
        # No gdocs CSS, just base
        gdocs_blocks = []
        base_css = parsed

    page_tpl, project_tpl, preamble_tpl, preamble_lists_tpl = _load_templates()

    # Compute inline HTML from runs or text for project sections
    for p in processed_projects:
        if p["type"] == "project":
            for sec_data in p.get("sections", {}).values():
                runs = sec_data.get("runs")
                if runs:
                    sec_data["inline_html"] = runs_to_inline_html(runs)
                elif sec_data.get("text"):
                    # Render from text with bold labels (PM format)
                    sec_data["inline_html"] = _render_section_html(sec_data["text"])
                else:
                    sec_data["inline_html"] = sec_data.get("html", "")
            # Header: bold 11pt, no underline (matches PM format)
            header = p.get("header", {})
            header_text = header.get("text", "")
            if header_text:
                escaped = (header_text.replace("&", "&amp;")
                           .replace("<", "&lt;").replace(">", "&gt;"))
                header["inline_html"] = (
                    f'<h3 style="font-size:11pt;font-weight:700;font-family:Calibri,sans-serif;'
                    f'margin-top:0;margin-bottom:2pt">{escaped}</h3>'
                )
            else:
                header["inline_html"] = header.get("html", "")

    rendered_blocks = []
    for p in processed_projects:
        block_html = render_project(p, project_tpl, preamble_tpl, preamble_lists_tpl)
        rendered_blocks.append({"html": block_html})

    # Render HTML (template now uses external canonical.css)
    html = page_tpl.render(blocks=rendered_blocks)

    out_path = config.SITE_DIR / "index.html"
    out_path.write_text(html, encoding="utf-8")

    # Collect all classes used in the rendered HTML to prune CSS
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    used_classes = set()
    for el in soup.find_all(class_=True):
        for cls in el.get("class", []):
            used_classes.add(cls)

    # Build and write canonical CSS
    canonical_css = _prune_gdocs_rules(gdocs_blocks, used_classes, base_css)
    canonical_path = config.ASSETS_DIR / "canonical.css"
    canonical_path.write_text(canonical_css, encoding="utf-8")

    inlined_path = _generate_inlined(html, canonical_css)

    return str(out_path), inlined_path


def _generate_inlined(html, canonical_css):
    from premailer import transform

    # Replace the external link with an inline <style> block
    html_with_style = re.sub(
        r'<link\s+rel="stylesheet"\s+href="[^"]*"[^>]*>',
        f"<style>\n{canonical_css}\n</style>",
        html,
        count=1,
    )
    # Strip control characters that break lxml/premailer
    html_with_style = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', html_with_style)
    inlined = transform(
        html_with_style,
        remove_classes=False,
        strip_important=False,
        keep_style_tags=False,
        disable_validation=True,
    )
    out_path = config.SITE_DIR / "index_pasteable.html"
    out_path.write_text(inlined, encoding="utf-8")
    return str(out_path)


def generate_json(processed_projects):
    import json

    records = []
    for p in processed_projects:
        if p["type"] in ("preamble", "preamble-lists"):
            continue
        rec = {
            "uid": p["uid"],
            "slug": p["slug"],
            "fingerprint": p["fingerprint"],
            "fields": p["fields"],
            "contacts": p.get("contacts_text", "TBC"),
            "artists": p.get("artists_text", "TBC"),
            "bfa_phase": p.get("bfa_phase_canonical", "TBC"),
            "next_steps": p.get("next_steps", []),
        }
        # Add sections with text + runs for downstream consumers
        sections_out = {}
        for sec_name, sec_data in p.get("sections", {}).items():
            sec_rec = {"text": sec_data.get("text", "")}
            runs = sec_data.get("runs")
            if runs:
                sec_rec["runs"] = [
                    {k: v for k, v in r.items() if v or k == "text"}
                    for r in runs
                ]
            sections_out[sec_name] = sec_rec
        if sections_out:
            rec["sections"] = sections_out
        records.append(rec)

    config.SITE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = config.SITE_DIR / "projects.json"
    out_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(out_path)


def render_one(project_data: dict) -> str:
    """Render a single project through the full pipeline, returning inlined HTML.

    Reuses the same template + premailer path as render_site / _generate_inlined
    so the iframe preview matches the pasteable output exactly.
    """
    import re as _re
    from premailer import transform

    # 1. Compute styled runs for each section (using gdocs CSS if available)
    gdocs_css_path = config.ASSETS_DIR / "gdocs.css"
    gdocs_css = ""
    if gdocs_css_path.exists():
        gdocs_css = gdocs_css_path.read_text(encoding="utf-8")
    resolver = StyleResolver(gdocs_css)
    for sec_data in project_data.get("sections", {}).values():
        html = sec_data.get("html", "")
        if html.strip() and "runs" not in sec_data:
            sec_data["runs"] = walk_html_for_runs(html, resolver)

    # 2. Build inline_html from runs or text (same as render_site)
    for sec_data in project_data.get("sections", {}).values():
        runs = sec_data.get("runs")
        if runs:
            sec_data["inline_html"] = runs_to_inline_html(runs)
        elif sec_data.get("text"):
            sec_data["inline_html"] = _render_section_html(sec_data["text"])
        else:
            sec_data["inline_html"] = sec_data.get("html", "")

    # 3. Build header inline_html (matches PM format: bold 11pt, no underline)
    header = project_data.get("header", {})
    header_text = header.get("text", "")
    if header_text:
        escaped = (header_text.replace("&", "&amp;")
                   .replace("<", "&lt;").replace(">", "&gt;"))
        header["inline_html"] = (
            f'<h3 style="font-size:11pt;font-weight:700;font-family:Calibri,sans-serif;'
            f'margin-top:0;margin-bottom:2pt">{escaped}</h3>'
        )
    else:
        header["inline_html"] = header.get("html", "")

    # 4. Render through project template
    _, project_tpl, preamble_tpl, preamble_lists_tpl = _load_templates()
    block_html = render_project(project_data, project_tpl, preamble_tpl, preamble_lists_tpl)

    # 5. Load CSS: prefer canonical.css (from prior full render), else base.css
    canonical_path = config.ASSETS_DIR / "canonical.css"
    base_css_path = config.TEMPLATE_DIR / "base.css"
    if canonical_path.exists():
        css = canonical_path.read_text(encoding="utf-8")
    elif base_css_path.exists():
        css = base_css_path.read_text(encoding="utf-8")
    else:
        css = ""

    # 6. Wrap in a minimal HTML document
    doc_html = (
        f'<!DOCTYPE html>\n'
        f'<html><head><meta charset="utf-8">\n'
        f'<style>\n{css}\n</style>\n'
        f'</head>\n'
        f'<body class="doc-content">\n'
        f'{block_html}\n'
        f'</body></html>'
    )

    # 7. Inline styles via premailer (same options as _generate_inlined)
    doc_html = _re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', doc_html)
    inlined = transform(
        doc_html,
        remove_classes=False,
        strip_important=False,
        keep_style_tags=False,
        disable_validation=True,
    )
    return inlined


def _update_preamble_date(projects: list) -> None:
    """Update the heading date in the main preamble to today."""
    import re
    from datetime import datetime

    now = datetime.now()
    today = f"{now.strftime('%B')} {now.day}, {now.year}"

    for p in projects:
        if p.get("type") != "preamble":
            continue
        content = p.get("sections", {}).get("content", {})
        text = content.get("text", "")
        html = content.get("html", "")
        # Replace "To Do List <Month Day, Year>" with current date
        pattern = r"To Do List\s+\w+ \d{1,2},?\s*\d{4}"
        replacement = f"To Do List {today}"
        if re.search(pattern, text):
            content["text"] = re.sub(pattern, replacement, text)
        if re.search(pattern, html):
            content["html"] = re.sub(pattern, replacement, html)


def render_all(projects, gdocs_css):
    """Compute styled runs + render site + JSON + GDocs inject.

    Shared entry point used by both run.py and reconcile.py.
    """
    _update_preamble_date(projects)

    resolver = StyleResolver(gdocs_css)
    for p in projects:
        for sec_data in p.get("sections", {}).values():
            # Skip runs generation for sections with labeled text content —
            # _render_section_html handles those with bold label formatting.
            if sec_data.get("text"):
                continue
            html = sec_data.get("html", "")
            if html.strip() and "runs" not in sec_data:
                sec_data["runs"] = walk_html_for_runs(html, resolver)

    html_path, pasteable_path = render_site(projects, gdocs_css)
    json_path = generate_json(projects)
    gdocs_path = generate_gdocs_json(projects)

    # Copy dashboard to site directory
    dash_src = config.TEMPLATE_DIR / "dashboard.html"
    dash_dst = config.SITE_DIR / "dashboard.html"
    if dash_src.exists():
        shutil.copy2(str(dash_src), str(dash_dst))

    return html_path, pasteable_path, json_path, gdocs_path
