"""Extract rich HTML from python-docx paragraph runs.

Two public functions for two data paths:
  - extract_project_paragraph_html: semantic HTML for project paragraphs
  - extract_preamble_paragraph_html: render-ready HTML with inline styles for preambles
"""

from docx.oxml.ns import qn

from .pipeline.style_resolver import _escape_html

# Word highlight color enum (WD_COLOR_INDEX int) → CSS hex
_HIGHLIGHT_MAP = {
    0: None,       # AUTO
    1: "#000000",  # BLACK
    2: "#0000ff",  # BLUE
    3: "#00ffff",  # TURQUOISE
    4: "#00ff00",  # BRIGHT_GREEN
    5: "#ff00ff",  # PINK
    6: "#ff0000",  # RED
    7: "#ffff00",  # YELLOW
    8: None,       # WHITE (skip — not visible)
    9: "#000080",  # DARK_BLUE
    10: "#008080", # TEAL
    11: "#008000", # GREEN
    12: "#800080", # VIOLET
    13: "#800000", # DARK_RED
    14: "#808000", # DARK_YELLOW
    15: "#808080", # GRAY_50
    16: "#c0c0c0", # GRAY_25
}


def _get_hyperlink_map(para):
    """Build {r:id → url} from paragraph's parent relationships."""
    rels = para.part.rels
    link_map = {}
    for hl in para._element.findall(qn("w:hyperlink")):
        rid = hl.get(qn("r:id"))
        if rid and rid in rels:
            link_map[rid] = (rels[rid].target_ref, hl)
    return link_map


def _run_to_html(run, href=None):
    """Convert a single docx Run to an HTML fragment with semantic tags."""
    text = run.text or ""
    if not text:
        return ""

    html = _escape_html(text)

    # Strikethrough
    if run.font.strike:
        html = f"<s>{html}</s>"
    # Italic
    if run.italic:
        html = f"<i>{html}</i>"
    # Bold
    if run.bold:
        html = f"<b>{html}</b>"

    # Color (non-black)
    color_rgb = None
    if run.font.color and run.font.color.rgb:
        c = str(run.font.color.rgb)
        if c not in ("000000", ""):
            color_rgb = f"#{c}"
    if color_rgb:
        html = f'<span style="color:{color_rgb}">{html}</span>'

    # Highlight
    hl_hex = None
    if run.font.highlight_color is not None:
        hl_int = int(run.font.highlight_color)
        hl_hex = _HIGHLIGHT_MAP.get(hl_int)
    # Also check shading (w:shd fill)
    if not hl_hex:
        rpr = run._element.find(qn("w:rPr"))
        if rpr is not None:
            shd = rpr.find(qn("w:shd"))
            if shd is not None:
                fill = shd.get(qn("w:fill"))
                if fill and fill.lower() not in ("auto", "000000", "ffffff", "none", ""):
                    hl_hex = f"#{fill}"
    if hl_hex:
        html = f'<span style="background-color:{hl_hex}">{html}</span>'

    # Hyperlink
    if href:
        html = f'<a href="{_escape_html(href)}">{html}</a>'

    return html


def _extract_runs_html(para):
    """Core run extraction shared by both project and preamble paths.

    Walks paragraph XML to handle both regular runs and hyperlinked runs
    in document order.

    Returns: list of HTML fragments (one per run/hyperlink group).
    """
    link_map = _get_hyperlink_map(para)
    fragments = []

    for child in para._element:
        tag = child.tag

        if tag == qn("w:r"):
            # Regular run (not inside a hyperlink)
            from docx.text.run import Run
            run = Run(child, para)
            # Check for w:br (line break)
            if child.find(qn("w:br")) is not None:
                fragments.append("<br/>")
            html = _run_to_html(run)
            if html:
                fragments.append(html)

        elif tag == qn("w:hyperlink"):
            rid = child.get(qn("r:id"))
            href = None
            if rid and rid in para.part.rels:
                href = para.part.rels[rid].target_ref
            # Process runs inside the hyperlink
            for r_el in child.findall(qn("w:r")):
                from docx.text.run import Run
                run = Run(r_el, para)
                if r_el.find(qn("w:br")) is not None:
                    fragments.append("<br/>")
                html = _run_to_html(run, href=href)
                if html:
                    fragments.append(html)

    return fragments


def extract_project_paragraph_html(para):
    """Extract semantic HTML from a project paragraph.

    Returns: (text, html) where text is plain .text and html is semantic HTML
    wrapped in <p> (no inline style — renderer controls sizing).
    Text has \\n replaced with space so one paragraph = one text line.
    """
    text = (para.text or "").replace("\n", " ")
    fragments = _extract_runs_html(para)
    inner = "".join(fragments)
    html = f"<p>{inner}</p>" if inner else "<p></p>"
    return text, html


def extract_preamble_paragraph_html(para):
    """Extract render-ready HTML from a preamble paragraph.

    Returns: (text, html) where html has inline styles on the <p> tag
    including font-size, bullet formatting, and bold headings.
    Text has \\n replaced with space so one paragraph = one text line.
    """
    text = (para.text or "").replace("\n", " ")
    fragments = _extract_runs_html(para)
    inner = "".join(fragments)

    # Determine font size from first run WITH TEXT CONTENT (default 11pt).
    # Skip whitespace-only/linebreak runs — they often inherit the paragraph's
    # default size (11pt) rather than the content size (8pt).
    font_size = "11pt"
    for run in para.runs:
        if run.font.size and (run.text or "").strip():
            pt = run.font.size / 12700
            font_size = f"{pt:.0f}pt"
            break

    # Base style
    styles = [
        "margin:0",
        f"font-size:{font_size}",
        "font-family:Calibri,sans-serif",
        "line-height:1.15",
        "color:#000",
    ]

    # Check for bullet (numPr in paragraph properties)
    pPr = para._element.find(qn("w:pPr"))
    has_bullet = False
    if pPr is not None:
        has_bullet = pPr.find(qn("w:numPr")) is not None

    if has_bullet:
        styles.append("margin-left:18pt")
        styles.append("text-indent:-12pt")
        inner = f"&#x25cf; {inner}"  # ● bullet

    # Bold heading: if first run is bold and it's the dominant formatting
    first_bold = False
    if para.runs:
        first_bold = bool(para.runs[0].bold)
    if first_bold and not has_bullet:
        # Check if it's a city heading (mostly bold, short text)
        all_bold = all(r.bold for r in para.runs if (r.text or "").strip())
        if all_bold:
            styles.append("font-weight:700")

    style_attr = ";".join(styles)
    html = f'<p style="{style_attr}">{inner}</p>'
    return text, html


class _PartProxy:
    """Minimal proxy so Paragraph(el, proxy).part works for hyperlink resolution."""
    def __init__(self, doc_part):
        self._doc_part = doc_part
    @property
    def part(self):
        return self._doc_part


def extract_table_html(tbl_element, doc_part):
    """Extract an HTML <table> from a w:tbl element.

    Returns: (text, html) where text is tab-separated cell text per row,
    and html is a styled <table>.
    """
    rows = tbl_element.findall(qn("w:tr"))
    text_lines = []
    html_rows = []
    proxy = _PartProxy(doc_part)

    for row in rows:
        cells = row.findall(qn("w:tc"))
        cell_texts = []
        cell_htmls = []
        for cell in cells:
            cell_text_parts = []
            cell_html_parts = []
            for p_el in cell.findall(qn("w:p")):
                from docx.text.paragraph import Paragraph
                para = Paragraph(p_el, proxy)
                t, h = extract_preamble_paragraph_html(para)
                cell_text_parts.append(t)
                # Strip outer <p> tag — we'll wrap in <td> instead
                inner = h
                if inner.startswith("<p ") and inner.endswith("</p>"):
                    start = inner.index(">") + 1
                    inner = inner[start:-4]
                cell_html_parts.append(inner)
            cell_texts.append(" ".join(cell_text_parts))
            cell_htmls.append("".join(cell_html_parts))

        text_lines.append("\t".join(cell_texts))
        row_html = "".join(
            f'<td style="padding:2pt 6pt;font-size:8pt;font-family:Calibri,sans-serif;border:1px solid #000">{ch}</td>'
            for ch in cell_htmls
        )
        html_rows.append(f"<tr>{row_html}</tr>")

    text = "\n".join(text_lines)
    html = (
        '<table style="border-collapse:collapse;font-size:8pt;font-family:Calibri,sans-serif;border:1px solid #000">'
        + "".join(html_rows)
        + "</table>"
    )
    return text, html


def extract_sdt_content(sdt_element, doc_part):
    """Extract content from a w:sdt (structured document tag).

    Returns list of (text, html) tuples — one per table or paragraph inside.
    """
    content = sdt_element.find(qn("w:sdtContent"))
    if content is None:
        return []

    proxy = _PartProxy(doc_part)
    results = []
    for child in content:
        tag = child.tag
        if tag == qn("w:tbl"):
            results.append(extract_table_html(child, doc_part))
        elif tag == qn("w:p"):
            from docx.text.paragraph import Paragraph
            para = Paragraph(child, proxy)
            results.append(extract_preamble_paragraph_html(para))
    return results


def iter_preamble_body_children(doc, start_idx, end_idx):
    """Walk body children (paragraphs, SDTs, tables) in range.

    Yields (text, html) tuples for each element. SDTs are unwrapped
    and their content extracted. Tables produce <table> HTML.
    """
    body = doc.element.body
    children = list(body)

    for i in range(start_idx, min(end_idx, len(children))):
        child = children[i]
        tag = child.tag

        if tag == qn("w:p"):
            from docx.text.paragraph import Paragraph
            para = Paragraph(child, doc.part)
            yield extract_preamble_paragraph_html(para)

        elif tag == qn("w:sdt"):
            for item in extract_sdt_content(child, doc.part):
                yield item

        elif tag == qn("w:tbl"):
            yield extract_table_html(child, doc.part)
