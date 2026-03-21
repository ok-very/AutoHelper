"""
Google Docs API injection JSON generator.

For each project, produces a batchUpdate-ready payload with:
  - insertText request (full flat text)
  - updateTextStyle requests for each styled range
"""

import json
from . import config
from .style_resolver import StyleResolver


def _build_project_payload(project):
    """Build a single project's batchUpdate payload."""
    header_text = project.get("header", {}).get("text", "")
    sections = project.get("sections", {})

    # Collect (text, primary_style) tuples from pre-computed runs
    all_runs = []  # (text, style_or_None)

    # Preferred section order for readability
    SECTION_ORDER = [
        "contacts", "governance", "artists", "artwork_title",
        "bfa_phase", "milestones", "next_steps", "fabrication",
        "unmapped",
    ]

    ordered_keys = []
    for key in SECTION_ORDER:
        if key in sections:
            ordered_keys.append(key)
    for key in sections:
        if key not in ordered_keys:
            ordered_keys.append(key)

    resolver = StyleResolver("")  # only used for get_primary_style

    for sec_key in ordered_keys:
        sec_data = sections[sec_key]
        runs = sec_data.get("runs")
        if not runs:
            continue

        for run in runs:
            text = run.get("text", "")
            styles = run.get("styles", [])
            rich = run.get("rich", {})
            primary = resolver.get_primary_style(styles)
            all_runs.append((text, primary, styles, rich))

        # ensure newline after each section
        if all_runs and not all_runs[-1][0].endswith("\n"):
            all_runs.append(("\n", None, [], {}))

    if not all_runs:
        return None

    # -- First pass: collapse runs into raw flat text + style ranges --
    raw_text = ""
    raw_ranges = []  # (start, end, style_type)
    raw_rich_ranges = []  # (start, end, rich_props_dict)

    for item in all_runs:
        text = item[0]
        style = item[1]
        all_styles = item[2] if len(item) > 2 else []
        rich = item[3] if len(item) > 3 else {}
        start = len(raw_text)
        raw_text += text
        end = len(raw_text)
        if start < end:
            # Emit all semantic styles (not just primary)
            for s in all_styles:
                raw_ranges.append((start, end, s))
            # If only primary was found and no all_styles
            if not all_styles and style:
                raw_ranges.append((start, end, style))
            # Rich properties (font-size, colors)
            if rich:
                raw_rich_ranges.append((start, end, rich))

    if not raw_text.strip():
        return None

    # -- Second pass: clean up line-by-line, rebuild with adjusted offsets --
    flat_text = ""
    style_ranges = []
    rich_style_ranges = []  # (start, end, rich_props)
    src_pos = 0

    for line in raw_text.split("\n"):
        stripped = line.strip()
        lead = len(line) - len(line.lstrip())

        content_start = src_pos + lead
        content_end = src_pos + lead + len(stripped)

        final = ""
        omap = []
        prev_space = False
        for ch in stripped:
            if ch == " " and prev_space:
                omap.append(len(final))
                continue
            final += ch
            omap.append(len(final) - 1)
            prev_space = ch == " "
        omap.append(len(final))

        dest_start = len(flat_text)

        for rs, re_, stype in raw_ranges:
            s = max(rs, content_start)
            e = min(re_, content_end)
            if s < e:
                local_s = s - content_start
                local_e = e - content_start
                if local_s < len(omap) and local_e < len(omap):
                    ds = dest_start + omap[local_s]
                    de = dest_start + omap[local_e]
                    if ds < de:
                        style_ranges.append((ds, de, stype))

        for rs, re_, rich in raw_rich_ranges:
            s = max(rs, content_start)
            e = min(re_, content_end)
            if s < e:
                local_s = s - content_start
                local_e = e - content_end
                if local_s < len(omap) and local_e + len(stripped) < len(omap):
                    local_e = e - content_start
                    if local_e > len(omap) - 1:
                        local_e = len(omap) - 1
                    ds = dest_start + omap[local_s]
                    de = dest_start + omap[min(local_e, len(omap) - 1)]
                    if ds < de:
                        rich_style_ranges.append((ds, de, rich))

        flat_text += final + "\n"
        src_pos += len(line) + 1

    # Collapse consecutive blank lines
    while "\n\n\n" in flat_text:
        flat_text = flat_text.replace("\n\n\n", "\n\n")

    flat_text = flat_text.strip("\n") + "\n"

    # Build requests
    requests = []

    requests.append({
        "insertText": {
            "location": {"index": "__COMPUTED__"},
            "text": flat_text,
        }
    })

    for start, end, style_type in style_ranges:
        if not flat_text[start:end].strip():
            continue
        text_style = {}
        fields = ""

        if style_type == "bold":
            text_style = {"bold": True}
            fields = "bold"
        elif style_type == "highlight":
            text_style = {
                "backgroundColor": {
                    "color": {
                        "rgbColor": {"red": 1, "green": 1, "blue": 0}
                    }
                }
            }
            fields = "backgroundColor"
        elif style_type == "red":
            text_style = {
                "foregroundColor": {
                    "color": {
                        "rgbColor": {"red": 1, "green": 0, "blue": 0}
                    }
                }
            }
            fields = "foregroundColor"
        elif style_type == "strikethrough":
            text_style = {"strikethrough": True}
            fields = "strikethrough"
        elif style_type == "italic":
            text_style = {"italic": True}
            fields = "italic"
        elif style_type == "underline":
            text_style = {"underline": True}
            fields = "underline"
        elif style_type == "link_blue":
            text_style = {
                "foregroundColor": {
                    "color": {
                        "rgbColor": {"red": 0.067, "green": 0.333, "blue": 0.8}
                    }
                }
            }
            fields = "foregroundColor"
        else:
            continue

        requests.append({
            "updateTextStyle": {
                "range": {
                    "startIndex": f"__OFFSET__+{start}",
                    "endIndex": f"__OFFSET__+{end}",
                },
                "textStyle": text_style,
                "fields": fields,
            }
        })

    # Rich style requests (font-size, background-color, foreground-color)
    def _hex_to_rgb(hex_color):
        h = hex_color.lstrip("#")
        return {
            "red": int(h[0:2], 16) / 255,
            "green": int(h[2:4], 16) / 255,
            "blue": int(h[4:6], 16) / 255,
        }

    for start, end, rich in rich_style_ranges:
        if not flat_text[start:end].strip():
            continue

        if "font_size_pt" in rich and rich["font_size_pt"] != 11:
            requests.append({
                "updateTextStyle": {
                    "range": {
                        "startIndex": f"__OFFSET__+{start}",
                        "endIndex": f"__OFFSET__+{end}",
                    },
                    "textStyle": {
                        "fontSize": {"magnitude": rich["font_size_pt"], "unit": "PT"}
                    },
                    "fields": "fontSize",
                }
            })

        if "bg_color" in rich:
            requests.append({
                "updateTextStyle": {
                    "range": {
                        "startIndex": f"__OFFSET__+{start}",
                        "endIndex": f"__OFFSET__+{end}",
                    },
                    "textStyle": {
                        "backgroundColor": {"color": {"rgbColor": _hex_to_rgb(rich["bg_color"])}}
                    },
                    "fields": "backgroundColor",
                }
            })

        if "fg_color" in rich:
            requests.append({
                "updateTextStyle": {
                    "range": {
                        "startIndex": f"__OFFSET__+{start}",
                        "endIndex": f"__OFFSET__+{end}",
                    },
                    "textStyle": {
                        "foregroundColor": {"color": {"rgbColor": _hex_to_rgb(rich["fg_color"])}}
                    },
                    "fields": "foregroundColor",
                }
            })

    # Sort updateTextStyle requests in reverse offset order to avoid drift
    insert_req = requests[0]
    style_reqs = requests[1:]
    style_reqs.sort(
        key=lambda r: int(r["updateTextStyle"]["range"]["startIndex"].split("+")[1]),
        reverse=True,
    )
    requests = [insert_req] + style_reqs

    return {
        "slug": project["slug"],
        "uid": project["uid"],
        "anchor_text": header_text,
        "requests": requests,
    }


def generate_gdocs_json(processed_projects):
    """Generate Google Docs API injection JSON for all projects.

    Returns the output file path.
    """
    payloads = []

    # Order: preambles → active projects → on-hold projects
    def _sort_key(p):
        ptype = p.get("type", "")
        if ptype == "preamble":
            return (0, "")
        if ptype == "preamble-lists":
            return (1, "")
        status = p.get("status", "active")
        name = p.get("fields", {}).get("project_name", "")
        if status == "on_hold":
            return (3, name)
        return (2, name)

    ordered = sorted(processed_projects, key=_sort_key)

    for p in ordered:
        payload = _build_project_payload(p)
        if payload:
            payloads.append(payload)

    config.SITE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = config.SITE_DIR / "gdocs_inject.json"
    out_path.write_text(
        json.dumps(payloads, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return str(out_path)
