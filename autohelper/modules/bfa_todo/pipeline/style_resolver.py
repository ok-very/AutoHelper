"""
CSS property-based style detection for Google Docs HTML.

Parses gdocs CSS to build a class→semantic-style map by inspecting
actual CSS properties (not hardcoded class names).  Walks HTML fragments
to produce styled runs suitable for inline rendering and GDocs injection.
"""

import re
from lxml import html as lxml_html


# CSS property → semantic style name
_PROPERTY_RULES = [
    # (property, value_pattern, semantic_name)
    ("font-weight", re.compile(r"^(700|800|900|bold)$"), "bold"),
    ("background-color", re.compile(r"#ff(ff00|f000|ff0e)"), "highlight"),
    ("color", re.compile(r"#ff0000"), "red"),
    ("color", re.compile(r"#1155cc"), "link_blue"),
    ("text-decoration", re.compile(r"line-through"), "strikethrough"),
    ("font-style", re.compile(r"^italic$"), "italic"),
    # Note: underline is NOT detected from CSS classes.  In Google Docs
    # exports, classes like c1/c9/c22 carry text-decoration:underline on
    # hundreds of spans (headers, sub-labels, body text) which produces
    # pervasive underlining.  Underline only enters the pipeline via:
    #   - <u> HTML tag  (see _TAG_STYLES)
    #   - link_blue  →  rendered with underline automatically
    #   - project headers  →  hardcoded in renderer.py
]

# HTML tags that imply a semantic style
_TAG_STYLES = {
    "strong": "bold",
    "b": "bold",
    "em": "italic",
    "i": "italic",
    "s": "strikethrough",
    "strike": "strikethrough",
    "u": "underline",
}

BLOCK_TAGS = frozenset({
    "p", "div", "li", "br", "h1", "h2", "h3", "h4", "h5", "h6", "tr",
})

LIST_TAGS = frozenset({"ul", "ol"})

# Priority order for GDocs API (only one style per range)
_STYLE_PRIORITY = [
    "highlight", "red", "strikethrough", "bold", "italic", "underline", "link_blue",
]


class StyleResolver:
    """Resolve Google Docs CSS class names to semantic styles."""

    def __init__(self, gdocs_css):
        self._class_map = {}  # {class_name: [semantic_styles]}
        if gdocs_css:
            self._parse_css(gdocs_css)

    def _parse_css(self, css):
        """Parse CSS text and build the class→styles map."""
        # Remove comments
        css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)

        # Extract rule blocks: .classname { declarations }
        for m in re.finditer(r"\.([\w-]+)\s*\{([^}]*)\}", css):
            cls_name = m.group(1)
            declarations = m.group(2)

            styles = set()
            for prop, val_re, sem_name in _PROPERTY_RULES:
                # Find property:value pairs
                prop_match = re.search(
                    rf"{re.escape(prop)}\s*:\s*([^;]+)", declarations
                )
                if prop_match:
                    val = prop_match.group(1).strip().lower()
                    if val_re.search(val):
                        styles.add(sem_name)

            if styles:
                self._class_map[cls_name] = sorted(styles)

    def resolve(self, class_str):
        """Return list of semantic styles for a space-separated class string."""
        if not class_str:
            return []
        styles = []
        seen = set()
        for cls in class_str.split():
            for s in self._class_map.get(cls, []):
                if s not in seen:
                    styles.append(s)
                    seen.add(s)
        return styles

    def get_primary_style(self, styles):
        """Return the single highest-priority style for GDocs API."""
        for s in _STYLE_PRIORITY:
            if s in styles:
                return s
        return None


def _collapse_ws(text):
    """Collapse runs of 2+ regular spaces/tabs to single space.

    Non-breaking spaces (U+00A0) are preserved — Google Docs uses
    them for tab-like columnar alignment (e.g. between PPAP/DPAP
    fields on the same line).
    """
    if not text:
        return text
    return re.sub(r"[ \t]{2,}", " ", text)


def walk_html_for_runs(html_str, resolver):
    """Parse an HTML fragment into styled runs.

    Returns a list of dicts:
        {"text": str, "styles": [str], "href": str|None, "list_level": int}

    Block elements produce newlines.  Styles are resolved from CSS
    classes (via resolver) and native HTML tags (<strong>, <em>, etc.).

    list_level > 0 indicates the run originated inside a <li> at that
    nesting depth.  ``runs_to_inline_html`` uses this to reconstruct
    ``<ul><li>`` markup instead of flat ``<p>`` paragraphs.
    """
    if not html_str or not html_str.strip():
        return []

    try:
        doc = lxml_html.fromstring(f"<div>{html_str}</div>")
    except Exception:
        text = re.sub(r"<[^>]+>", "", html_str).strip()
        return [{"text": text, "styles": [], "href": None, "list_level": 0}] if text else []

    runs = []

    def _walk(node, inherited_styles=None, inherited_href=None, list_depth=0):
        styles = list(inherited_styles or [])
        href = inherited_href

        # Track list nesting depth
        if node.tag == "li":
            list_depth = max(list_depth, 1)

        # Detect styles from CSS classes
        if node.tag == "span":
            class_str = node.get("class", "")
            for s in resolver.resolve(class_str):
                if s not in styles:
                    styles.append(s)

        # Detect styles from HTML tags
        tag_style = _TAG_STYLES.get(node.tag)
        if tag_style and tag_style not in styles:
            styles.append(tag_style)

        # Detect links
        if node.tag == "a":
            href = node.get("href")

        if node.text:
            runs.append({
                "text": _collapse_ws(node.text),
                "styles": list(styles),
                "href": href,
                "list_level": list_depth,
            })

        for child in node:
            _walk(child, styles, href, list_depth)
            if child.tail:
                # Tail text after a child reverts to parent context
                tail_depth = list_depth if node.tag == "li" else (list_depth if list_depth else 0)
                runs.append({
                    "text": _collapse_ws(child.tail),
                    "styles": list(inherited_styles or []),
                    "href": inherited_href,
                    "list_level": tail_depth,
                })

        # Insert newline after block elements
        if node.tag in BLOCK_TAGS:
            if runs and not runs[-1]["text"].endswith("\n"):
                runs.append({"text": "\n", "styles": [], "href": None, "list_level": 0})

    _walk(doc)
    return runs


def runs_to_inline_html(runs):
    """Convert styled runs back to HTML with inline style attributes.

    Paragraph structure is reconstructed from newline boundaries.
    List items (runs with list_level > 0) are wrapped in <ul><li>.
    """
    if not runs:
        return ""

    # Split runs into "blocks" at newline boundaries.
    # Each block carries its list_level from the first content run.
    blocks = []  # [(list_level, [runs])]
    current_runs = []
    current_list = 0

    for run in runs:
        text = run["text"]
        ll = run.get("list_level", 0)
        if "\n" in text:
            parts = text.split("\n")
            for i, part in enumerate(parts):
                if part:
                    current_runs.append({
                        "text": part,
                        "styles": run["styles"],
                        "href": run["href"],
                    })
                    if ll > 0:
                        current_list = ll
                if i < len(parts) - 1:
                    if current_runs:
                        blocks.append((current_list, current_runs))
                    current_runs = []
                    current_list = 0
        else:
            current_runs.append(run)
            if ll > 0:
                current_list = ll

    if current_runs:
        blocks.append((current_list, current_runs))

    # Render blocks, grouping consecutive list items into <ul>
    html_parts = []
    pending_lis = []

    def _flush_list():
        if pending_lis:
            html_parts.append("<ul>" + "".join(pending_lis) + "</ul>")
            pending_lis.clear()

    for list_level, block_runs in blocks:
        if not block_runs:
            continue
        if all(not r["text"].strip() for r in block_runs):
            continue

        rendered = _render_spans(block_runs)
        if not rendered:
            continue

        if list_level > 0:
            pending_lis.append(f"<li>{rendered}</li>")
        else:
            _flush_list()
            html_parts.append(f"<p>{rendered}</p>")

    _flush_list()
    return "\n".join(html_parts)


def _render_spans(block_runs):
    """Render a list of runs into span HTML (no wrapping <p>/<li>)."""
    spans = []
    for r in block_runs:
        text = _escape_html(r["text"])
        if not text:
            continue

        has_href = bool(r.get("href"))
        style_css = _styles_to_css(r["styles"], has_href=has_href)
        inner = text

        if has_href:
            inner = f'<a href="{_escape_attr(r["href"])}">{inner}</a>'

        if style_css:
            spans.append(f'<span style="{style_css}">{inner}</span>')
        else:
            spans.append(inner)

    return "".join(spans)


def _styles_to_css(styles, has_href=False):
    """Convert a list of semantic style names to a CSS style string."""
    if not styles and not has_href:
        return ""
    parts = []
    has_text_dec = False
    for s in styles:
        if s == "bold":
            parts.append("font-weight:700")
        elif s == "highlight":
            parts.append("background-color:#ffff00")
        elif s == "red":
            parts.append("color:#ff0000")
        elif s == "link_blue":
            parts.append("color:#1155cc")
            # Links get underline automatically
            if not has_text_dec:
                parts.append("text-decoration:underline")
                has_text_dec = True
        elif s == "strikethrough":
            if not has_text_dec:
                parts.append("text-decoration:line-through")
                has_text_dec = True
        elif s == "italic":
            parts.append("font-style:italic")
        elif s == "underline":
            if not has_text_dec:
                parts.append("text-decoration:underline")
                has_text_dec = True
    # Bare links (href but no link_blue) still get underline
    if has_href and not has_text_dec:
        parts.append("text-decoration:underline")
    return ";".join(parts)


def _escape_html(text):
    """Escape HTML special characters.  Preserves NBSPs as &nbsp;."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\u00a0", "&nbsp;")
    )


def _escape_attr(text):
    """Escape an HTML attribute value."""
    return (
        text.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
