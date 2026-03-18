"""
Apply reconciliation decisions to YAML project data.

Core rule: Excel overwrites structured fields. Narrative content is NEVER lost.
"""

import re
from . import config, utils


def _set_yaml_value(project, dotpath, value):
    """Set a value in a YAML project dict using dot notation."""
    parts = dotpath.split(".")
    obj = project
    for p in parts[:-1]:
        if p not in obj:
            obj[p] = {}
        obj = obj[p]
    obj[parts[-1]] = value


_KNOWN_LABELS = (
    r"(?:Project\s+)?Architect|Landscape(?:\s+Architect)?|"
    r"Fabricator|Contact|Developer(?:\s+Contact)?"
)


def _merge_labeled_line(text, label, new_value):
    """Replace a labeled value in multi-line text, or append if not found.

    Handles labels with prefix words (e.g., 'Project Architect:' for label 'Architect').
    Preserves adjacent labeled values on the same line — only replaces up to the
    next label boundary (comma/pipe before another 'Label:' pattern).
    """
    if not text:
        return f"{label}: {new_value}"

    lines = text.split("\n")
    for i, line in enumerate(lines):
        # Match the label (with optional prefix word) and colon
        match = re.search(
            rf"((?:\w+\s+)?{re.escape(label)}\s*:\s*)",
            line,
            re.IGNORECASE,
        )
        if not match:
            continue

        label_end = match.end()
        rest = line[label_end:]

        # Find next label boundary: comma/pipe followed by a known label pattern
        next_boundary = re.search(
            rf"[,|]\s*(?:{_KNOWN_LABELS})\s*:",
            rest,
            re.IGNORECASE,
        )

        if next_boundary:
            # Only replace up to the next label boundary
            lines[i] = line[:label_end] + new_value + rest[next_boundary.start():]
        else:
            # No other labels on this line; replace to end of line
            lines[i] = line[:label_end] + new_value

        return "\n".join(lines)

    # Label not found, append as new line
    return text.rstrip() + f"\n{label}: {new_value}"


def apply_decisions(decisions, match_report, diff_report, rollup_diffs,
                    yaml_projects_by_uid, aliases):
    """Apply approved reconciliation decisions.

    Returns:
        modified_uids: set of UIDs that were modified
        new_projects: list of new project dicts to add
        archived_uids: set of UIDs to archive
        alias_updates: list of new alias entries to add
    """
    modified_uids = set()
    new_projects = []
    archived_uids = set()
    alias_updates = []

    # 1. Apply field changes
    field_decisions = decisions.get("field_changes", {})
    for idx_str, action in field_decisions.items():
        if action != "accept":
            continue
        idx = int(idx_str)
        if idx >= len(diff_report.get("field_changes", [])):
            continue
        change = diff_report["field_changes"][idx]
        uid = change["uid"]
        project = yaml_projects_by_uid.get(uid)
        if not project:
            continue

        field = change["field"]
        new_val = change["new"]

        # Handle contact merge fields
        if field.startswith("contacts_text."):
            label = field.split(".", 1)[1]
            old_text = project.get("contacts_text", "")
            # Extract just the value part from "Label: value"
            val_part = new_val
            if ": " in new_val:
                val_part = new_val.split(": ", 1)[1]
            project["contacts_text"] = _merge_labeled_line(old_text, label, val_part)
        elif field.startswith("artists_text."):
            label = field.split(".", 1)[1]
            old_text = project.get("artists_text", "")
            val_part = new_val
            if ": " in new_val:
                val_part = new_val.split(": ", 1)[1]
            project["artists_text"] = _merge_labeled_line(old_text, label, val_part)
        elif field == "artwork_title":
            # Update the section text, preserve HTML
            if "sections" in project and "artwork_title" in project["sections"]:
                project["sections"]["artwork_title"]["text"] = new_val
        else:
            _set_yaml_value(project, field, new_val)

        modified_uids.add(uid)

    # 2. Apply rollup decisions
    rollup_decisions = decisions.get("rollups", {})
    for idx_str, action in rollup_decisions.items():
        if action != "accept":
            continue
        idx = int(idx_str)
        if idx >= len(rollup_diffs or []):
            continue
        rollup = rollup_diffs[idx]

        # Apply to primary UID and any secondary UIDs
        all_uids = [rollup["uid"]] + rollup.get("also_applies_to", [])
        for uid in all_uids:
            project = yaml_projects_by_uid.get(uid)
            if not project:
                continue
            for change in rollup.get("changes", []):
                _set_yaml_value(project, change["field"], change["new"])
            modified_uids.add(uid)

    # 3. Handle new projects
    new_decisions = decisions.get("new_projects", {})
    new_in_excel = match_report.get("new_in_excel", [])
    for idx_str, action in new_decisions.items():
        if action != "accept":
            continue
        idx = int(idx_str)
        if idx >= len(new_in_excel):
            continue
        excel_row = new_in_excel[idx]["excel_row"]
        new_proj = _create_project_from_excel(excel_row)
        new_projects.append(new_proj)

        # Add alias entry
        alias_updates.append({
            "excel_name": excel_row["raw_name"],
            "uid": new_proj["uid"],
            "notes": "Auto-created from Excel import",
        })

    # 4. Handle pipeline-only projects
    pipeline_decisions = decisions.get("pipeline_only", {})
    pipeline_only = match_report.get("pipeline_only", [])
    for idx_str, action in pipeline_decisions.items():
        if action != "archive":
            continue
        idx = int(idx_str)
        if idx >= len(pipeline_only):
            continue
        archived_uids.add(pipeline_only[idx]["uid"])

    # 5. Handle ambiguous matches
    ambiguous_decisions = decisions.get("ambiguous", {})
    ambiguous = match_report.get("ambiguous", [])
    for idx_str, action in ambiguous_decisions.items():
        idx = int(idx_str)
        if idx >= len(ambiguous):
            continue
        entry = ambiguous[idx]

        if action == "confirm":
            # Treat as a matched pair — add alias
            alias_updates.append({
                "excel_name": entry["excel_row"]["raw_name"],
                "uid": entry["best_uid"],
                "notes": f"Confirmed fuzzy match (score={entry['score']})",
            })
        elif action == "new":
            # Create new project
            excel_row = entry["excel_row"]
            new_proj = _create_project_from_excel(excel_row)
            new_projects.append(new_proj)
            alias_updates.append({
                "excel_name": excel_row["raw_name"],
                "uid": new_proj["uid"],
                "notes": "Created as new (rejected fuzzy match)",
            })

    return modified_uids, new_projects, archived_uids, alias_updates


def _create_project_from_excel(excel_row):
    """Create a minimal YAML project module from an Excel row."""
    client = excel_row["client"]
    project = excel_row["project"]
    municipality = excel_row.get("municipality", "")

    fingerprint = utils.make_fingerprint(client, project, municipality)
    uid = utils.stable_uid(fingerprint)
    slug = utils.make_slug(client, project, municipality)

    # Build contacts text from available fields
    contacts_parts = []
    if excel_row.get("developer_contact"):
        contacts_parts.append(f"Contact: {excel_row['developer_contact']}")
    if excel_row.get("architect"):
        contacts_parts.append(f"Architect: {excel_row['architect']}")
    if excel_row.get("landscape_architect"):
        contacts_parts.append(f"Landscape: {excel_row['landscape_architect']}")
    contacts_text = "\n".join(contacts_parts) if contacts_parts else "TBC"

    # Build artists text
    artists_parts = []
    if excel_row.get("selected_artist"):
        artists_parts.append(f"Selected Artist: {excel_row['selected_artist']}")
    if excel_row.get("fabricator"):
        artists_parts.append(f"Fabricator: {excel_row['fabricator']}")
    artists_text = "\n".join(artists_parts) if artists_parts else "TBD"

    # Build header text
    owner = excel_row.get("bfa_lead", "BFA")
    budget_str = excel_row.get("project_budget", "$TBC")
    install_str = excel_row.get("target_completion", "TBC")
    header_text = (
        f"({owner}) {client}: {project}"
        + (f", {municipality}" if municipality else "")
        + f" ({budget_str})"
        + f" Install: {install_str}"
    )

    return {
        "uid": uid,
        "slug": slug,
        "fingerprint": fingerprint,
        "type": "project",
        "fields": {
            "owner_team": owner,
            "client": client,
            "project_name": project,
            "city": municipality or "TBC",
            "art_budget": excel_row.get("artist_fee", "$TBC"),
            "total_budget": excel_row.get("project_budget", "$TBC"),
            "bfa_fee": excel_row.get("consultant_fee", "$TBC"),
            "install_date": install_str,
        },
        "sections": {},
        "header": {
            "text": header_text,
            "html": f"<h3>{header_text}</h3>",
        },
        "contacts_text": contacts_text,
        "artists_text": artists_text,
        "bfa_phase_display": excel_row.get("project_phase", "TBC"),
        "bfa_phase_canonical": excel_row.get("project_phase", "TBC"),
        "next_steps": [],
        "source": "excel",
    }
