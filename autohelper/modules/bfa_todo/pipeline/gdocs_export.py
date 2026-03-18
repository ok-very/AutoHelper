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
            primary = resolver.get_primary_style(styles)
            all_runs.append((text, primary))

        # ensure newline after each section
        if all_runs and not all_runs[-1][0].endswith("\n"):
            all_runs.append(("\n", None))

    if not all_runs:
        return None

    # -- First pass: collapse runs into raw flat text + style ranges --
    raw_text = ""
    raw_ranges = []  # (start, end, style_type)

    for text, style in all_runs:
        start = len(raw_text)
        raw_text += text
        end = len(raw_text)
        if style and start < end:
            raw_ranges.append((start, end, style))

    if not raw_text.strip():
        return None

    # -- Second pass: clean up line-by-line, rebuild with adjusted offsets --
    flat_text = ""
    style_ranges = []
    src_pos = 0  # position in raw_text

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
                ds = dest_start + omap[local_s]
                de = dest_start + omap[local_e]
                if ds < de:
                    style_ranges.append((ds, de, stype))

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

    for p in processed_projects:
        if p["type"] in ("preamble", "preamble-lists"):
            continue

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
