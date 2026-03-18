"""
Match Excel rows to existing YAML pipeline entries.

Matching priority:
1. Exact alias lookup (aliases.yaml mappings)
2. Rollup group membership (aliases.yaml rollups)
3. Ignored list check (aliases.yaml ignored)
4. Auto-match via fuzzy fingerprint comparison (0.85 threshold)
5. Client alias expansion before fuzzy match
"""

from . import config, utils


FUZZY_THRESHOLD = 0.85
AMBIGUOUS_THRESHOLD = 0.65


def _build_alias_index(aliases):
    """Build lookup dicts from aliases data."""
    # excel_name -> uid
    name_to_uid = {}
    for m in aliases.get("mappings", []):
        name_to_uid[m["excel_name"]] = m["uid"]

    # excel_name -> (rollup_uid, rollup_entry)
    name_to_rollup = {}
    for r in aliases.get("rollups", []):
        for ename in r.get("excel_names", []):
            name_to_rollup[ename] = (r["uid"], r)

    # ignored excel_names
    ignored_names = set()
    for entry in aliases.get("ignored", []):
        ignored_names.add(entry["excel_name"])

    # client aliases
    client_aliases = aliases.get("client_aliases", {})

    return name_to_uid, name_to_rollup, ignored_names, client_aliases


def _build_yaml_fingerprints(yaml_projects):
    """Build fingerprint index from YAML projects for fuzzy matching."""
    fps = {}  # uid -> fingerprint string
    for p in yaml_projects:
        if p.get("type") != "project":
            continue
        uid = p["uid"]
        client = p.get("fields", {}).get("client", "")
        project_name = p.get("fields", {}).get("project_name", "")
        city = p.get("fields", {}).get("city", "")
        fp = f"{client}|{project_name}|{city}".lower()
        fps[uid] = fp
    return fps


def _excel_fingerprint(row, client_aliases):
    """Build fingerprint from Excel row for fuzzy comparison."""
    client = row["client"]
    # Expand client alias
    expanded = client_aliases.get(client, client)
    project = row["project"]
    municipality = row.get("municipality", "")
    return f"{expanded}|{project}|{municipality}".lower()


def match(excel_rows, yaml_projects, aliases):
    """Match Excel rows to YAML entries.

    Returns a MatchReport dict:
    {
        "matched": [{"excel_row": {...}, "uid": "...", "source": "alias|rollup|fuzzy"}],
        "rollup_groups": [{"uid": "...", "label": "...", "excel_rows": [...], "strategy": "..."}],
        "new_in_excel": [{"excel_row": {...}}],
        "pipeline_only": [{"uid": "...", "slug": "...", "phase": "..."}],
        "ambiguous": [{"excel_row": {...}, "best_uid": "...", "score": 0.87, "yaml_label": "..."}],
    }
    """
    name_to_uid, name_to_rollup, ignored_names, client_aliases = _build_alias_index(aliases)
    yaml_fps = _build_yaml_fingerprints(yaml_projects)

    # Track which UIDs have been matched
    matched_uids = set()
    rollup_uids = set()

    result = {
        "matched": [],
        "rollup_groups": {},  # uid -> group info (temp dict, converted to list later)
        "new_in_excel": [],
        "pipeline_only": [],
        "ambiguous": [],
        "ignored": [],
    }

    for row in excel_rows:
        ename = row["raw_name"]

        # 1. Check ignored list
        if ename in ignored_names:
            result["ignored"].append({"excel_row": row, "reason": "ignored list"})
            continue

        # 2. Check rollup membership
        if ename in name_to_rollup:
            uid, rollup_entry = name_to_rollup[ename]
            if uid not in result["rollup_groups"]:
                result["rollup_groups"][uid] = {
                    "uid": uid,
                    "label": rollup_entry["label"],
                    "strategy": rollup_entry.get("strategy", "merge_all"),
                    "also_applies_to": rollup_entry.get("also_applies_to", []),
                    "excel_rows": [],
                }
            result["rollup_groups"][uid]["excel_rows"].append(row)
            rollup_uids.add(uid)
            # Also track secondary UIDs so they don't appear as pipeline-only
            for secondary_uid in rollup_entry.get("also_applies_to", []):
                rollup_uids.add(secondary_uid)
            continue

        # 3. Check exact alias
        if ename in name_to_uid:
            uid = name_to_uid[ename]
            result["matched"].append({
                "excel_row": row,
                "uid": uid,
                "source": "alias",
            })
            matched_uids.add(uid)
            continue

        # 4. Fuzzy match
        excel_fp = _excel_fingerprint(row, client_aliases)
        best_score = 0.0
        best_uid = None
        best_label = ""

        for uid, yaml_fp in yaml_fps.items():
            if uid in matched_uids or uid in rollup_uids:
                continue
            score = utils.fuzzy_match_score(excel_fp, yaml_fp)
            if score > best_score:
                best_score = score
                best_uid = uid
                best_label = yaml_fp

        if best_score >= FUZZY_THRESHOLD:
            result["matched"].append({
                "excel_row": row,
                "uid": best_uid,
                "source": "fuzzy",
                "score": round(best_score, 3),
            })
            matched_uids.add(best_uid)
        elif best_score >= AMBIGUOUS_THRESHOLD:
            result["ambiguous"].append({
                "excel_row": row,
                "best_uid": best_uid,
                "score": round(best_score, 3),
                "yaml_label": best_label,
            })
        else:
            result["new_in_excel"].append({"excel_row": row})

    # Convert rollup_groups dict to list
    result["rollup_groups"] = list(result["rollup_groups"].values())

    # Build cross-check index: which clients have matched/rollup projects
    matched_clients = {}  # client_lower -> list of project labels
    for entry in result["matched"]:
        row = entry["excel_row"]
        client_key = row["client"].lower().strip()
        matched_clients.setdefault(client_key, []).append(
            f"{row['client']} - {row['project']}"
        )
    for group_data in result["rollup_groups"]:
        for row in group_data["excel_rows"]:
            client_key = row["client"].lower().strip()
            matched_clients.setdefault(client_key, []).append(group_data["label"])

    # Find pipeline-only projects (in YAML but not matched by any Excel row)
    all_matched = matched_uids | rollup_uids
    seen_pipeline_uids = set()
    for p in yaml_projects:
        if p.get("type") != "project":
            continue
        uid = p["uid"]
        if uid not in all_matched and uid not in seen_pipeline_uids:
            seen_pipeline_uids.add(uid)
            client = p.get("fields", {}).get("client", "TBC")
            entry = {
                "uid": uid,
                "slug": p.get("slug", ""),
                "phase": p.get("bfa_phase_canonical", "TBC"),
                "client": client,
                "project_name": p.get("fields", {}).get("project_name", "TBC"),
            }
            # Cross-check: flag if client has other matched projects
            client_key = client.lower().strip()
            related = matched_clients.get(client_key, [])
            if related:
                entry["related_matched"] = related[:3]  # first 3
            result["pipeline_only"].append(entry)

    return result
