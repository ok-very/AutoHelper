"""Map Monday.com board data to AutoHelper project pipeline structures."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from .types import MondayBoardData, MondayItem, StagedCorrespondence

logger = logging.getLogger(__name__)

# Monday group stage → BFA template stage mapping
# Monday groups use the same stage numbering as BFA templates,
# but some Monday groups map to a different BFA stage (e.g., "Stage 4: SP#2" → BFA stage 6)
_GROUP_STAGE_OVERRIDES: dict[str, int] = {
    "community engagement": 4,       # Stage 3 Community Engagement → BFA stage 4
    "artist concept proposals": 6,   # Stage 4 SP#2 → BFA stage 6
    "artist longlist": 5,            # Stage 4 SP#1 → BFA stage 5
    "detailed design": 8,            # Stage 6 Detailed Design → BFA stage 8
    "artwork management to 50%": 9,  # Stage 6 50% → BFA stage 9
    "artwork management to 100%": 9, # Stage 6 100% → BFA stage 9
    "installation": 10,              # Stage 7 → BFA stage 10
    "plaque": 11,                    # Stage 8 → BFA stage 11
    "legal letters": 11,
    "photography": 11,
    "final documentation": 11,
}


def _infer_bfa_stage(group_title: str) -> int | None:
    """Map Monday group title to BFA template stage number."""
    # Check overrides first (matches on lowercase group title suffix)
    lower = group_title.lower()
    for key, stage in _GROUP_STAGE_OVERRIDES.items():
        if key in lower:
            return stage
    # Fall back to parsed stage number
    m = re.match(r"Stage\s+(\d+)", group_title, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _normalize_name(name: str) -> str:
    """Normalize a task name for fuzzy matching."""
    s = name.lower().strip()
    # Remove common prefixes/suffixes that differ between Monday and BFA
    s = re.sub(r"\(client\)|\(if applicable\)", "", s)
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _token_overlap(a: str, b: str) -> float:
    """Compute Jaccard similarity between two normalized names."""
    tokens_a = set(a.split())
    tokens_b = set(b.split())
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def _load_template_tasks() -> list[dict]:
    """Load BFA template tasks from bfa_templates.json."""
    from importlib import resources
    data_pkg = resources.files("autohelper") / "data" / "bfa_templates.json"
    data = json.loads(data_pkg.read_text(encoding="utf-8"))
    return data["tasks"]


def match_items_to_template(board: MondayBoardData) -> dict[str, str]:
    """Fuzzy match Monday items to BFA template temp_ids.

    Returns {monday_item_id: temp_id}.
    Matches by item name + group stage. Exact match first, then token overlap.
    """
    template_tasks = _load_template_tasks()

    # Build stage → [(temp_id, normalized_name, email_template_key)] index
    by_stage: dict[int, list[tuple[str, str, str | None]]] = {}
    for t in template_tasks:
        stage = t.get("stage", 0)
        by_stage.setdefault(stage, []).append(
            (t["temp_id"], _normalize_name(t["name"]), t.get("email_template_key"))
        )

    result: dict[str, str] = {}

    for item in board.items:
        bfa_stage = _infer_bfa_stage(item.group_title)
        if bfa_stage is None:
            continue

        candidates = by_stage.get(bfa_stage, [])
        if not candidates:
            continue

        item_norm = _normalize_name(item.name)

        # Exact match
        for temp_id, cand_name, _ in candidates:
            if item_norm == cand_name:
                result[item.id] = temp_id
                break
        else:
            # Token overlap — take best match above threshold
            best_score = 0.0
            best_id = ""
            for temp_id, cand_name, _ in candidates:
                score = _token_overlap(item_norm, cand_name)
                if score > best_score:
                    best_score = score
                    best_id = temp_id
            if best_score >= 0.4 and best_id:
                result[item.id] = best_id

    logger.info(
        "Matched %d/%d Monday items to BFA template tasks",
        len(result), len(board.items),
    )
    return result


def get_template_key_map() -> dict[str, str]:
    """Return {temp_id: email_template_key} for all template tasks that have one."""
    return {
        t["temp_id"]: t["email_template_key"]
        for t in _load_template_tasks()
        if t.get("email_template_key")
    }


def derive_phase(board: MondayBoardData) -> str:
    """Derive current BFA phase from group/item completion status.

    Finds the lowest stage that has incomplete items.
    """
    from autohelper.modules.bfa_todo.pipeline.config import STAGE_TO_PHASE

    completed_statuses = {"completed", "executed", "done"}

    # Group items by BFA stage
    stage_items: dict[int, list[MondayItem]] = {}
    for item in board.items:
        stage = _infer_bfa_stage(item.group_title)
        if stage is not None:
            stage_items.setdefault(stage, []).append(item)

    if not stage_items:
        return "TBC"

    # Find the current stage — lowest stage with incomplete items
    for stage in sorted(stage_items.keys()):
        items = stage_items[stage]
        all_complete = all(i.status.lower() in completed_statuses for i in items)
        if not all_complete:
            return STAGE_TO_PHASE.get(stage, f"Stage {stage}")

    # All stages complete
    max_stage = max(stage_items.keys())
    return STAGE_TO_PHASE.get(max_stage, f"Stage {max_stage}")


def board_to_intake(board: MondayBoardData, municipality: str) -> dict[str, Any]:
    """Map Monday board to IntakeAnswers-compatible dict."""
    return {
        "municipality": municipality,
        "project_name": f"{board.developer} - {board.project}" if board.project else board.name,
        "developer_name": board.developer or None,
    }


def extract_pm_contact(board: MondayBoardData) -> dict | None:
    """Extract PM name from people column."""
    pm_names: set[str] = set()
    for item in board.items:
        if item.pm_name:
            pm_names.add(item.pm_name)

    if not pm_names:
        return None

    # Take the most common PM name
    name = max(pm_names, key=lambda n: sum(1 for i in board.items if i.pm_name == n))
    parts = name.strip().split()
    return {
        "full_name": name,
        "first_name": parts[0] if parts else name,
        "last_name": " ".join(parts[1:]) if len(parts) > 1 else "",
        "source": "monday_import",
    }


def collect_correspondence(
    board: MondayBoardData,
    item_to_temp: dict[str, str],
) -> list[StagedCorrespondence]:
    """Collect updates + subitem email templates, tagged with temp_id.

    Each record becomes a comment on the matched ClickUp task after provisioning.
    """
    key_map = get_template_key_map()
    records: list[StagedCorrespondence] = []

    for item in board.items:
        temp_id = item_to_temp.get(item.id)
        if not temp_id:
            continue

        template_key = key_map.get(temp_id)

        # Item updates → correspondence
        for update in item.updates:
            if not update.body_text and not update.body_html:
                continue
            records.append(StagedCorrespondence(
                temp_id=temp_id,
                template_key=template_key,
                content=update.body_text or "",
                content_html=update.body_html or None,
                source="update",
                created_at=update.created_at or None,
                creator=update.creator_name or None,
            ))

        # Subitem email templates → correspondence
        for si in item.subitems:
            if si.email_template:
                records.append(StagedCorrespondence(
                    temp_id=temp_id,
                    template_key=template_key,
                    content=si.email_template,
                    content_html=None,
                    source="email_template",
                    created_at=None,
                    creator=None,
                ))

    logger.info("Collected %d correspondence records from board %s", len(records), board.id)
    return records


def collect_file_links(board: MondayBoardData) -> list[dict]:
    """Sweep all items + subitems + update bodies for SharePoint/OneDrive URLs."""
    links: list[dict] = []
    sharepoint_re = re.compile(r"https?://[^\s\"'>]+(?:sharepoint|onedrive)[^\s\"'>]*", re.IGNORECASE)

    for item in board.items:
        stage = _infer_bfa_stage(item.group_title)

        # Item files
        for url in item.files:
            links.append({"url": url, "item_name": item.name, "stage": stage, "context": "item_file"})

        # Subitem files
        for si in item.subitems:
            for url in si.files:
                links.append({"url": url, "item_name": f"{item.name}/{si.name}", "stage": stage, "context": "subitem_file"})

        # URLs in update bodies
        for update in item.updates:
            for url in sharepoint_re.findall(update.body_html or ""):
                links.append({"url": url, "item_name": item.name, "stage": stage, "context": "update_link"})

        # URLs in notes
        if item.notes:
            for url in sharepoint_re.findall(item.notes):
                links.append({"url": url, "item_name": item.name, "stage": stage, "context": "notes_link"})

    # Deduplicate by URL
    seen: set[str] = set()
    deduped: list[dict] = []
    for link in links:
        if link["url"] not in seen:
            seen.add(link["url"])
            deduped.append(link)

    logger.info("Collected %d unique file links from board %s", len(deduped), board.id)
    return deduped


# ── Overview board mapping ──────────────────────────────────────────

MONDAY_MUNICIPALITY_MAP: dict[str, str] = {
    "North Vancouver (District)": "north-vancouver-district",
    "North Vancouver (City)": "north-vancouver-city",
    "City of Vancouver": "vancouver",
    "City of New Westminster": "new-westminster",
    "City of Richmond": "richmond",
    "City of Surrey": "surrey",
    "City of Abbotsford": "abbotsford",
    "City of Prince Rupert": "prince-rupert",
    "City of Burnaby": "burnaby",
    "City of Port Moody": "port-moody",
}

# Overview column IDs (from board 18034877971)
_OV = {
    "person": "person",
    "phase": "status",
    "state": "color_mkw5gj9w",
    "municipality": "color_mkw3129z",
    "address": "text_mkw3ec4r",
    "billing_entity": "text_mm08mnft",
    "developer_contact": "long_text_mkw3mezt",
    "architect": "dropdown_mkw3tqjs",
    "landscape": "dropdown_mkw3tx70",
    "selection_panel": "dropdown_mkw3qtdg",
    "community_advisors": "dropdown_mkw3qtdg",  # Note: may share ID with selection_panel
    "shortlisted_artists": "dropdown_mkw3vax2",
    "artist": "text_mkw3gmzj",
    "artwork_title": "text_mkw3gvv1",
    "fabricator": "dropdown_mkxdhgzp",
    "total_budget": "numeric_mkwjg4js",
    "art_budget": "numeric_mkwjt6yw",
    "consultant_fee": "numeric_mkwj4177",
    "target_completion": "text_mkw3qs66",
    "project_board_link": "link_mkwh3gkt",
    "project_folder_link": "link_mkw3rxyj",
    "selection_process": "color_mm07gjxv",
    "notes": "long_text_mkxc3aza",
    "dp_issuance": "date_mkwkw296",
    "sp1_date": "date_mkwt40tq",
    "artist_orientation_date": "date_mkwthh3j",
    "sp2_date": "date_mkwtx7jv",
    "kickoff_date": "date_mkx13r63",
    "contract_signed_date": "date_mm01ktpz",
    "occupancy_date": "date_mkxjmcs6",
}


def _get_ov(col_values: list[dict], key: str) -> str:
    """Get text value from an overview row by our key name."""
    col_id = _OV.get(key, "")
    for cv in col_values:
        if cv["id"] == col_id:
            return cv.get("text") or ""
    return ""


def _parse_link_url(col_values: list[dict], key: str) -> str:
    """Extract URL from a link-type column."""
    col_id = _OV.get(key, "")
    for cv in col_values:
        if cv["id"] == col_id:
            text = cv.get("text") or ""
            # Link text format: "Label - URL" or just URL
            if " - http" in text:
                return text.split(" - http", 1)[1]
                # Actually the text is "Label - URL", but the URL part includes "http"
            val = cv.get("value")
            if val:
                import json as _json
                try:
                    parsed = _json.loads(val)
                    return parsed.get("url") or ""
                except (ValueError, TypeError):
                    pass
            return text
    return ""


def _split_names(text: str) -> list[str]:
    """Split a comma or newline separated contact list into individual names."""
    if not text:
        return []
    # Split on commas and newlines
    parts = re.split(r"[,\n]", text)
    names = []
    for p in parts:
        clean = p.strip()
        # Remove parenthetical role info like "(Anthem)" but keep the name
        if clean and clean not in ("TBC", "TBD", ""):
            names.append(clean)
    return names


def _extract_board_id_from_link(link_text: str) -> str | None:
    """Extract Monday board ID from a project board link URL."""
    m = re.search(r"monday\.com/boards/(\d+)", link_text)
    return m.group(1) if m else None


def overview_row_to_project(item: dict[str, Any]) -> dict[str, Any]:
    """Map an overview board row to a rich project dict.

    Returns all extractable data: identity, municipality, phase, contacts,
    budgets, links, and the linked project board ID.
    """
    cvs = item.get("column_values", [])
    name = item.get("name", "")
    group = (item.get("group") or {}).get("title", "")

    # Parse developer/project from name
    parts = name.split(" - ", 1)
    developer = parts[0].strip() if parts else name
    project = parts[1].strip() if len(parts) > 1 else ""

    # Municipality
    municipality_raw = _get_ov(cvs, "municipality")
    municipality = MONDAY_MUNICIPALITY_MAP.get(municipality_raw, municipality_raw.lower().replace(" ", "-"))

    # Project board link → board ID
    board_link = _parse_link_url(cvs, "project_board_link")
    project_board_id = _extract_board_id_from_link(board_link) if board_link else None

    # Budgets
    total_raw = _get_ov(cvs, "total_budget")
    art_raw = _get_ov(cvs, "art_budget")

    def _parse_num(s: str) -> float | None:
        if not s:
            return None
        try:
            return float(re.sub(r"[^\d.]", "", s))
        except ValueError:
            return None

    # Contacts
    developer_contacts = _split_names(_get_ov(cvs, "developer_contact"))
    architect = _get_ov(cvs, "architect")
    landscape = _get_ov(cvs, "landscape")
    selection_panel = _split_names(_get_ov(cvs, "selection_panel"))
    shortlisted_artists = _split_names(_get_ov(cvs, "shortlisted_artists"))
    selected_artist = _get_ov(cvs, "artist")
    fabricator = _get_ov(cvs, "fabricator")

    return {
        "monday_item_id": item.get("id", ""),
        "name": name,
        "developer": developer,
        "project": project,
        "group": group,
        "municipality": municipality,
        "municipality_raw": municipality_raw,
        "phase": _get_ov(cvs, "phase"),
        "state": _get_ov(cvs, "state"),
        "address": _get_ov(cvs, "address"),
        "billing_entity": _get_ov(cvs, "billing_entity"),
        "total_budget": _parse_num(total_raw),
        "art_budget": _parse_num(art_raw),
        "consultant_fee": _parse_num(_get_ov(cvs, "consultant_fee")),
        "target_completion": _get_ov(cvs, "target_completion"),
        "install_date": _get_ov(cvs, "target_completion"),
        "pm_name": _get_ov(cvs, "person"),
        "selection_process": _get_ov(cvs, "selection_process"),
        "project_board_id": project_board_id,
        "project_board_link": board_link,
        "project_folder_link": _parse_link_url(cvs, "project_folder_link"),
        "notes": _get_ov(cvs, "notes"),
        # Contact slots
        "contacts": {
            "contact": developer_contacts,
            "architect": [architect] if architect else [],
            "landscape": [landscape] if landscape else [],
            "selection_panel": selection_panel,
            "shortlisted_artist": shortlisted_artists,
            "selected_artist": [selected_artist] if selected_artist else [],
            "fabricator": [fabricator] if fabricator else [],
        },
        # Milestone dates
        "dates": {
            "dp_issuance": _get_ov(cvs, "dp_issuance"),
            "sp1": _get_ov(cvs, "sp1_date"),
            "artist_orientation": _get_ov(cvs, "artist_orientation_date"),
            "sp2": _get_ov(cvs, "sp2_date"),
            "kickoff": _get_ov(cvs, "kickoff_date"),
            "contract_signed": _get_ov(cvs, "contract_signed_date"),
            "occupancy": _get_ov(cvs, "occupancy_date"),
        },
        "artwork_title": _get_ov(cvs, "artwork_title"),
    }
