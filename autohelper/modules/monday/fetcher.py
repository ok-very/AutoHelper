"""Fetch Monday.com board data via GraphQL API."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from autohelper.modules.context.monday import MondayClient

from .types import (
    MondayBoardData,
    MondayColumn,
    MondayGroup,
    MondayItem,
    MondaySubitem,
    MondayUpdate,
)

logger = logging.getLogger(__name__)


def _parse_stage(group_title: str) -> int | None:
    """Extract stage number from group title like 'Stage 3: DPAP'."""
    m = re.match(r"Stage\s+(\d+)", group_title, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _extract_column_value(col_values: list[dict], col_id: str) -> str:
    """Get text value for a column by ID."""
    for cv in col_values:
        if cv["id"] == col_id:
            return cv.get("text") or ""
    return ""


def _extract_column_value_by_type(col_values: list[dict], col_type: str) -> str:
    """Get text value for the first column matching a type."""
    for cv in col_values:
        if cv.get("type") == col_type:
            return cv.get("text") or ""
    return ""


def _find_status_col_id(columns: list[MondayColumn]) -> str:
    """Find the project_status column ID (status type with 'Task Status' or 'project_status')."""
    for c in columns:
        if c.id == "project_status" or (c.type == "status" and "task status" in c.title.lower()):
            return c.id
    # Fallback: first status column
    for c in columns:
        if c.type == "status":
            return c.id
    return ""


def _find_col_id(columns: list[MondayColumn], col_type: str, title_hint: str = "") -> str:
    """Find column ID by type and optional title hint."""
    if title_hint:
        for c in columns:
            if c.type == col_type and title_hint.lower() in c.title.lower():
                return c.id
    for c in columns:
        if c.type == col_type:
            return c.id
    return ""


def _extract_files(col_values: list[dict]) -> list[str]:
    """Extract file URLs from file-type column values."""
    urls: list[str] = []
    for cv in col_values:
        if cv.get("type") == "file" and cv.get("text"):
            # File text is the URL
            urls.append(cv["text"])
        elif cv.get("type") == "file" and cv.get("value"):
            try:
                val = json.loads(cv["value"])
                for f in val.get("files", []):
                    url = f.get("url") or f.get("publicUrl") or ""
                    if url:
                        urls.append(url)
            except (json.JSONDecodeError, TypeError):
                pass
    return urls


OVERVIEW_BOARD_ID = "18034877971"


def fetch_overview_rows(client: MondayClient) -> list[dict[str, Any]]:
    """Fetch all rows from the Current Projects Overview board with column values."""
    all_items: list[dict] = []

    first_page = client.query("""
        query($boardId: [ID!]!) {
            boards(ids: $boardId) {
                items_page(limit: 500) {
                    cursor
                    items {
                        id
                        name
                        group { id title }
                        column_values { id type text value }
                    }
                }
            }
        }
    """, {"boardId": [OVERVIEW_BOARD_ID]})

    page = first_page["boards"][0]["items_page"]
    all_items.extend(page["items"])
    cursor = page.get("cursor")

    while cursor:
        next_page = client.query("""
            query($cursor: String!) {
                next_items_page(limit: 500, cursor: $cursor) {
                    cursor
                    items {
                        id
                        name
                        group { id title }
                        column_values { id type text value }
                    }
                }
            }
        """, {"cursor": cursor})
        np = next_page["next_items_page"]
        all_items.extend(np["items"])
        cursor = np.get("cursor")

    logger.info("Fetched %d rows from overview board", len(all_items))
    return all_items


def fetch_board_list(client: MondayClient) -> list[dict[str, Any]]:
    """Fetch all active boards, filtered to project boards."""
    result = client.query("""
        query {
            boards(limit: 200, state: active) {
                id
                name
                items_count
            }
        }
    """)
    boards = result.get("boards", [])
    out = []
    for b in boards:
        name = b["name"]
        # Skip subitems boards and internal boards
        if name.startswith("Subitems of"):
            continue
        developer, project, item_type = MondayClient._parse_board_name(name)
        out.append({
            "id": b["id"],
            "name": name,
            "developer": developer,
            "project": project,
            "item_type": item_type,
            "items_count": b.get("items_count", 0),
        })
    return out


def fetch_board_full(client: MondayClient, board_id: str) -> MondayBoardData:
    """Fetch complete board data: groups, columns, items with values, subitems, updates."""

    # Step 1: Board metadata — groups + columns
    meta = client.query("""
        query($boardId: [ID!]!) {
            boards(ids: $boardId) {
                name
                columns { id title type settings_str }
                groups { id title }
            }
        }
    """, {"boardId": [board_id]})

    board_data = meta["boards"][0]
    board_name = board_data["name"]
    developer, project, _ = MondayClient._parse_board_name(board_name)

    columns = [
        MondayColumn(
            id=c["id"], title=c["title"], type=c["type"],
            settings=json.loads(c.get("settings_str") or "{}"),
        )
        for c in board_data["columns"]
    ]

    groups = [
        MondayGroup(id=g["id"], title=g["title"], stage=_parse_stage(g["title"]))
        for g in board_data["groups"]
    ]

    # Identify key column IDs
    status_col = _find_status_col_id(columns)
    people_col = _find_col_id(columns, "people", "PM") or _find_col_id(columns, "people")
    date_col = _find_col_id(columns, "date")
    notes_col = _find_col_id(columns, "text", "Notes") or _find_col_id(columns, "text")
    label_col = _find_col_id(columns, "status", "Label")
    timeline_col = _find_col_id(columns, "timeline")

    # Step 2: Fetch all items with pagination
    all_raw_items: list[dict] = []
    first_page = client.query("""
        query($boardId: [ID!]!) {
            boards(ids: $boardId) {
                items_page(limit: 500) {
                    cursor
                    items {
                        id
                        name
                        group { id title }
                        column_values { id type text value }
                        subitems {
                            id
                            name
                            column_values { id type text value }
                        }
                    }
                }
            }
        }
    """, {"boardId": [board_id]})

    page = first_page["boards"][0]["items_page"]
    all_raw_items.extend(page["items"])
    cursor = page.get("cursor")

    while cursor:
        next_page = client.query("""
            query($cursor: String!) {
                next_items_page(limit: 500, cursor: $cursor) {
                    cursor
                    items {
                        id
                        name
                        group { id title }
                        column_values { id type text value }
                        subitems {
                            id
                            name
                            column_values { id type text value }
                        }
                    }
                }
            }
        """, {"cursor": cursor})
        np = next_page["next_items_page"]
        all_raw_items.extend(np["items"])
        cursor = np.get("cursor")

    logger.info("Fetched %d items from board %s (%s)", len(all_raw_items), board_id, board_name)

    # Step 3: Fetch updates for items that likely have them (batch by ID)
    item_ids = [item["id"] for item in all_raw_items]
    updates_by_item: dict[str, list[MondayUpdate]] = {}

    # Batch in groups of 25 to avoid query complexity limits
    for i in range(0, len(item_ids), 25):
        batch_ids = item_ids[i : i + 25]
        try:
            updates_result = client.query("""
                query($itemIds: [ID!]!) {
                    items(ids: $itemIds) {
                        id
                        updates(limit: 50) {
                            id
                            body
                            text_body
                            created_at
                            creator { name }
                        }
                    }
                }
            """, {"itemIds": batch_ids})

            for item_data in updates_result.get("items", []):
                item_id = item_data["id"]
                updates = []
                for u in item_data.get("updates", []):
                    updates.append(MondayUpdate(
                        id=u["id"],
                        body_html=u.get("body") or "",
                        body_text=u.get("text_body") or "",
                        created_at=u.get("created_at") or "",
                        creator_name=(u.get("creator") or {}).get("name") or "",
                    ))
                if updates:
                    updates_by_item[item_id] = updates
        except Exception as e:
            logger.warning("Failed to fetch updates for batch starting at %d: %s", i, e)

    # Step 4: Assemble items
    items: list[MondayItem] = []
    for raw in all_raw_items:
        cvs = raw.get("column_values", [])
        group = raw.get("group", {})

        # Parse subitems
        subitems: list[MondaySubitem] = []
        for si in raw.get("subitems", []):
            si_cvs = si.get("column_values", [])
            subitems.append(MondaySubitem(
                id=si["id"],
                name=si["name"],
                status=_extract_column_value_by_type(si_cvs, "status"),
                people=_extract_column_value_by_type(si_cvs, "people") or None,
                target_date=_extract_column_value_by_type(si_cvs, "date") or None,
                notes=_extract_column_value_by_type(si_cvs, "text") or None,
                email_template=_extract_column_value_by_type(si_cvs, "long_text") or None,
                files=_extract_files(si_cvs),
            ))

        items.append(MondayItem(
            id=raw["id"],
            name=raw["name"],
            group_id=group.get("id", ""),
            group_title=group.get("title", ""),
            status=_extract_column_value(cvs, status_col) if status_col else "",
            pm_name=_extract_column_value(cvs, people_col) or None if people_col else None,
            target_date=_extract_column_value(cvs, date_col) or None if date_col else None,
            notes=_extract_column_value(cvs, notes_col) or None if notes_col else None,
            label=_extract_column_value(cvs, label_col) or None if label_col else None,
            timeline=_extract_column_value(cvs, timeline_col) or None if timeline_col else None,
            subitems=subitems,
            updates=updates_by_item.get(raw["id"], []),
            files=_extract_files(cvs),
        ))

    return MondayBoardData(
        id=board_id,
        name=board_name,
        developer=developer,
        project=project,
        groups=groups,
        columns=columns,
        items=items,
    )
