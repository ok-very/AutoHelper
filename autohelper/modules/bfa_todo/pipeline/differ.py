"""
Field-level change detection between matched Excel/YAML pairs.

Authority rules:
- Excel overwrites: phase, budgets, install_date, city, contacts (structured), artists (structured)
- Doc ONLY (never touch): next_steps, governance, fabrication, header HTML, all section HTML
"""

import re
from . import config, utils


# Fields where Excel is authoritative (Excel field -> YAML path)
EXCEL_AUTHORITY_FIELDS = {
    "project_phase": "bfa_phase_canonical",
    "project_budget": "fields.total_budget",
    "artist_fee": "fields.art_budget",
    "target_completion": "fields.install_date",
    "municipality": "fields.city",
    "project_state": "project_state",
}

# Contact-related fields that merge into contacts_text
CONTACT_MERGE_FIELDS = {
    "architect": "Architect",
    "landscape_architect": "Landscape",
    "fabricator": "Fabricator",
    "developer_contact": "Contact",
}

# Artist-related fields
ARTIST_MERGE_FIELDS = {
    "selected_artist": "Selected Artist",
    "fabricator": "Fabricator",
}

# Phase ordering for regression detection
PHASE_ORDER = {phase: idx for idx, phase in enumerate(config.VALID_PHASES)}

# Patterns that indicate rich contact detail beyond a bare name
_DETAIL_PATTERNS = re.compile(
    r"[/|]"                     # slash or pipe separator (multiple people/firms)
    r"|@"                       # email
    r"|\d{3}[\-.\s]\d{3}"      # phone number fragment
    r"|\(.*\w{3,}.*\)"         # parenthetical with 3+ char word (role/company)
    , re.IGNORECASE
)


def _get_yaml_value(project, dotpath):
    """Get a value from a YAML project dict using dot notation."""
    parts = dotpath.split(".")
    obj = project
    for p in parts:
        if isinstance(obj, dict):
            obj = obj.get(p)
        else:
            return None
    return obj


def _normalize_budget(val):
    """Normalize budget string for comparison."""
    if val is None:
        return "$TBC"
    s = str(val).strip()
    if not s or s.lower() in ("tbc", "tbd", "$tbc"):
        return "$TBC"
    # Strip $ and commas, convert to int for comparison
    clean = re.sub(r"[$,\s]", "", s)
    try:
        num = int(float(clean))
        return f"${num:,}"
    except (ValueError, TypeError):
        return s


def _budget_change_pct(old_val, new_val):
    """Calculate % change between two budget values. Returns None if can't compare."""
    def to_num(v):
        if not v or v == "$TBC":
            return None
        clean = re.sub(r"[$,\s]", "", str(v))
        try:
            return float(clean)
        except (ValueError, TypeError):
            return None

    old_num = to_num(old_val)
    new_num = to_num(new_val)
    if old_num and new_num and old_num > 0:
        return abs(new_num - old_num) / old_num
    return None


def _detect_phase_regression(old_phase, new_phase):
    """Check if new phase is earlier than old phase."""
    old_idx = PHASE_ORDER.get(old_phase, -1)
    new_idx = PHASE_ORDER.get(new_phase, -1)
    if old_idx >= 0 and new_idx >= 0 and new_idx < old_idx:
        return True
    return False


def diff_matched(matched_entries, yaml_projects_by_uid):
    """Compare matched Excel/YAML pairs and return field-level changes.

    Args:
        matched_entries: list of {"excel_row": {...}, "uid": "..."} from matcher
        yaml_projects_by_uid: dict of uid -> YAML project data

    Returns:
        DiffReport dict with field_changes, warnings, stats
    """
    field_changes = []
    warnings = []

    for entry in matched_entries:
        excel = entry["excel_row"]
        uid = entry["uid"]
        yaml_proj = yaml_projects_by_uid.get(uid)
        if not yaml_proj:
            warnings.append({
                "uid": uid,
                "message": f"UID not found in YAML: {uid}",
                "severity": "error",
            })
            continue

        project_label = f"{excel['client']} - {excel['project']}"

        # Compare authority fields
        for excel_field, yaml_path in EXCEL_AUTHORITY_FIELDS.items():
            excel_val = excel.get(excel_field, "")
            yaml_val = _get_yaml_value(yaml_proj, yaml_path)

            # Normalize for comparison
            if "budget" in excel_field or "fee" in excel_field:
                excel_norm = _normalize_budget(excel_val)
                yaml_norm = _normalize_budget(yaml_val)
            else:
                excel_norm = str(excel_val).strip() if excel_val else ""
                yaml_norm = str(yaml_val).strip() if yaml_val else ""

            if not excel_norm or excel_norm in ("TBC", "$TBC"):
                continue  # Don't overwrite with empty/TBC

            if excel_norm == yaml_norm:
                continue  # No change

            # Phase-specific checks
            severity = "info"
            if yaml_path == "bfa_phase_canonical":
                # Migrate old phase for comparison
                old_migrated = utils.migrate_phase(yaml_norm)
                if old_migrated == excel_norm:
                    continue  # Same after migration
                if _detect_phase_regression(excel_norm, old_migrated):
                    severity = "warning"

            # Budget change check
            if "budget" in yaml_path or "art_budget" in yaml_path:
                pct = _budget_change_pct(yaml_norm, excel_norm)
                if pct is not None and pct > 0.5:
                    severity = "critical"

            field_changes.append({
                "uid": uid,
                "project_label": project_label,
                "field": yaml_path,
                "excel_field": excel_field,
                "old": yaml_norm or "TBC",
                "new": excel_norm,
                "severity": severity,
            })

        # Compare contact merge fields
        for excel_field, label in CONTACT_MERGE_FIELDS.items():
            excel_val = excel.get(excel_field, "").strip()
            if not excel_val:
                continue
            contacts_text = yaml_proj.get("contacts_text", "")

            # Check if the core value (names) is already present
            # Split multi-line Excel values and check each name
            excel_names = [n.strip() for n in re.split(r"[,\n]+", excel_val) if n.strip()]
            all_present = all(
                _name_present_in_text(name, contacts_text)
                for name in excel_names
            ) if excel_names else True
            if all_present:
                continue

            old_line = _extract_labeled_value(contacts_text, label)

            # Detect detail loss: old value has phone/email/role/multi-person info
            severity = "info"
            if old_line and _DETAIL_PATTERNS.search(old_line):
                severity = "warning"

            field_changes.append({
                "uid": uid,
                "project_label": project_label,
                "field": f"contacts_text.{label}",
                "excel_field": excel_field,
                "old": f"{label}: {old_line}" if old_line else f"(no {label} line)",
                "new": f"{label}: {excel_val}",
                "severity": severity,
            })

        # Compare artist field
        excel_artist = excel.get("selected_artist", "").strip()
        if excel_artist:
            artists_text = yaml_proj.get("artists_text", "")
            if excel_artist.lower() not in artists_text.lower():
                field_changes.append({
                    "uid": uid,
                    "project_label": project_label,
                    "field": "artists_text.Selected Artist",
                    "excel_field": "selected_artist",
                    "old": artists_text[:80] if artists_text else "TBC",
                    "new": f"Selected Artist: {excel_artist}",
                    "severity": "info",
                })

        # Artwork title — extract just the title line, ignoring BFA status lines
        excel_title = excel.get("artwork_title", "").strip()
        if excel_title:
            yaml_title_sec = yaml_proj.get("sections", {}).get("artwork_title", {})
            yaml_title_full = yaml_title_sec.get("text", "").strip() if yaml_title_sec else ""
            yaml_title_line = _extract_title_line(yaml_title_full)
            if (excel_title.lower() != yaml_title_line.lower()
                    and yaml_title_line
                    and yaml_title_line.lower() not in ("tbc", "tbd")):
                field_changes.append({
                    "uid": uid,
                    "project_label": project_label,
                    "field": "artwork_title",
                    "excel_field": "artwork_title",
                    "old": yaml_title_line,
                    "new": excel_title,
                    "severity": "info",
                })

    # Compute stats
    projects_affected = len(set(c["uid"] for c in field_changes))
    stats = {
        "total_changes": len(field_changes),
        "projects_affected": projects_affected,
        "warnings": len(warnings),
    }

    return {
        "field_changes": field_changes,
        "warnings": warnings,
        "stats": stats,
    }


def diff_rollups(rollup_groups, yaml_projects_by_uid):
    """Compute merged values for rollup groups.

    For each rollup group:
    - Phase: highest-numbered phase among members
    - Budget: sum across group
    - Artists: union of all artist names
    - State: "On Track" only if ALL rows On Track, else worst state
    """
    results = []
    state_priority = {
        "Trouble": 0, "Issues": 1, "Receivership": 2,
        "On Hold": 3, "Low Activity": 4, "On Track": 5,
    }

    for group in rollup_groups:
        uid = group["uid"]
        yaml_proj = yaml_projects_by_uid.get(uid)
        excel_rows = group["excel_rows"]

        # Merge phase: highest numbered
        best_phase_idx = -1
        best_phase = "TBC"
        for row in excel_rows:
            phase = row.get("project_phase", "TBC")
            idx = PHASE_ORDER.get(phase, -1)
            if idx > best_phase_idx:
                best_phase_idx = idx
                best_phase = phase

        # Merge budget: sum
        total_budget = 0
        total_artist_fee = 0
        has_budget = False
        for row in excel_rows:
            for field, accum in [("project_budget", "total"), ("artist_fee", "artist")]:
                val = row.get(field, "$TBC")
                clean = re.sub(r"[$,\s]", "", str(val))
                try:
                    num = float(clean)
                    if accum == "total":
                        total_budget += num
                    else:
                        total_artist_fee += num
                    has_budget = True
                except (ValueError, TypeError):
                    pass

        # Merge artists: union
        artists = set()
        for row in excel_rows:
            a = row.get("selected_artist", "").strip()
            if a:
                artists.add(a)

        # Merge state: worst
        worst_priority = 999
        worst_state = "TBC"
        for row in excel_rows:
            st = row.get("project_state", "TBC")
            pri = state_priority.get(st, 6)
            if pri < worst_priority:
                worst_priority = pri
                worst_state = st

        merged = {
            "phase": best_phase,
            "total_budget": f"${total_budget:,.0f}" if has_budget else "$TBC",
            "artist_fee": f"${total_artist_fee:,.0f}" if has_budget else "$TBC",
            "artists": sorted(artists),
            "state": worst_state,
        }

        # Compare with existing YAML
        changes = []
        if yaml_proj:
            old_phase = yaml_proj.get("bfa_phase_canonical", "TBC")
            migrated = utils.migrate_phase(old_phase)
            if migrated != merged["phase"] and merged["phase"] != "TBC":
                changes.append({
                    "field": "bfa_phase_canonical",
                    "old": old_phase,
                    "new": merged["phase"],
                })

            old_budget = _normalize_budget(
                _get_yaml_value(yaml_proj, "fields.total_budget")
            )
            if old_budget != merged["total_budget"] and merged["total_budget"] != "$TBC":
                changes.append({
                    "field": "fields.total_budget",
                    "old": old_budget,
                    "new": merged["total_budget"],
                })

        results.append({
            "uid": uid,
            "also_applies_to": group.get("also_applies_to", []),
            "label": group["label"],
            "strategy": group["strategy"],
            "excel_row_count": len(excel_rows),
            "merged": merged,
            "changes": changes,
        })

    return results


def _extract_labeled_value(text, label):
    """Extract the value portion after 'Label:' from multi-line text.

    Handles cases where the label is embedded mid-line (e.g.,
    'Project Architect: Name, Landscape Architect: Name').
    Returns just the value, not the full line.
    """
    if not text:
        return ""
    # Try to find "Label:" as a standalone label at line start or after comma/pipe
    pattern = re.compile(
        rf"(?:^|[,|])\s*(?:\w+\s+)?{re.escape(label)}\s*:\s*([^,|\n]+)",
        re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(text)
    if match:
        return match.group(1).strip()

    # Fallback: look for the label anywhere
    for line in text.split("\n"):
        if label.lower() + ":" in line.lower():
            idx = line.lower().index(label.lower() + ":")
            after = line[idx + len(label) + 1:].strip()
            # Trim at next label boundary
            next_label = re.search(r"\s+\w+:", after)
            if next_label:
                after = after[:next_label.start()].strip()
            return after
    return ""


def _extract_title_line(full_text):
    """Extract just the artwork title from section text.

    Skips lines starting with 'BFA Project Status:', 'Occupancy',
    'Send', or other operational notes.
    """
    if not full_text:
        return ""
    skip_prefixes = (
        "bfa project", "occupancy", "send ", "install", "on track",
        "on hold", "working towards", "project phase", "bfa phase",
    )
    lines = full_text.split("\n")
    title_parts = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if any(lower.startswith(p) for p in skip_prefixes):
            break  # Status lines come after the title; stop here
        title_parts.append(stripped)
    return " ".join(title_parts) if title_parts else full_text.split("\n")[0].strip()


def _name_present_in_text(name, text):
    """Check if a person/company name is present in text.

    Handles partial matches — e.g., 'Integra Architecture' matches
    'Integra Architecture / Collin Truong'. Splits on common delimiters.
    """
    if not name or not text:
        return False
    # Normalize
    name_lower = name.strip().lower()
    text_lower = text.lower()
    # Direct substring
    if name_lower in text_lower:
        return True
    # Try first+last name (handle 'First Last (Company)' format)
    core_name = re.sub(r"\s*\([^)]*\)\s*", "", name_lower).strip()
    if core_name and core_name in text_lower:
        return True
    # Try last name only for longer names
    parts = core_name.split()
    if len(parts) >= 2 and parts[-1] in text_lower:
        return True
    return False
