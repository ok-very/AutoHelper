"""
DEPRECATED: This module has been ported to AutoHelper.
Please use `autohelper.modules.context` instead.

Monday.com API integration
"""

import warnings
warnings.warn(
    "This module is deprecated. Use `autohelper.modules.context` instead.",
    DeprecationWarning,
    stacklevel=2
)

import os
import json
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from .monday_client import MondayClient, MondayClientError, get_client
from .monday_connector import (
    MondayConnector,
    MondayBoardSchema,
    MondayDataNode,
    MondayColumnValue as ConnectorColumnValue,
    MONDAY_TYPE_TO_RENDER_HINT,
    get_connector,
)


@dataclass
class BoardInfo:
    """Monday.com board information"""
    id: str
    name: str
    developer: str
    project: str
    item_type: str
    columns: List[Dict] = field(default_factory=list)
    groups: List[Dict] = field(default_factory=list)


@dataclass
class ColumnValue:
    """Parsed column value"""
    id: str
    title: str
    type: str
    value: Any
    text: str  # Human-readable text
    render_hint: str = "text"  # NEW: render hint from connector


def _make_request(query: str, variables: Optional[Dict] = None) -> Dict:
    """
    Make a GraphQL request to Monday.com API.

    Uses the new MondayClient for all requests.
    Returns dict with 'data' key on success, or 'error' key on failure.
    """
    try:
        client = get_client()
        data = client.query(query, variables)
        return {"data": data}
    except MondayClientError as e:
        return {"error": str(e), "details": e.errors}
    except Exception as e:
        return {"error": str(e)}


def parse_board_name(name: str) -> tuple[str, str, str]:
    """
    Parse board name: Developer - Project - Item
    Returns: (developer, project, item_type)
    """
    parts = name.split(" - ")
    if len(parts) >= 3:
        return parts[0].strip(), parts[1].strip(), " - ".join(parts[2:]).strip()
    elif len(parts) == 2:
        return parts[0].strip(), parts[1].strip(), ""
    else:
        return name, "", ""


# ============================================================
# BOARD QUERIES
# ============================================================

def search_boards(search_term: str, limit: int = 20) -> Dict:
    """
    Search for boards by name (partial match).
    Returns boards matching the search term.
    """
    query = """
    query ($limit: Int!) {
        boards(limit: $limit) {
            id
            name
            state
            workspace_id
            columns {
                id
                title
                type
                settings_str
            }
            groups {
                id
                title
            }
        }
    }
    """

    result = _make_request(query, {"limit": 100})  # Get more to filter

    if "error" in result:
        return result

    boards = result.get("data", {}).get("boards", [])
    search_lower = search_term.lower()

    matched = []
    for board in boards:
        if search_lower in board["name"].lower():
            developer, project, item_type = parse_board_name(board["name"])
            # Add render_hint to columns
            columns_with_hints = []
            for col in board.get("columns", []):
                col_copy = dict(col)
                col_copy["render_hint"] = MONDAY_TYPE_TO_RENDER_HINT.get(col["type"], "text")
                columns_with_hints.append(col_copy)

            matched.append({
                "id": board["id"],
                "name": board["name"],
                "developer": developer,
                "project": project,
                "item_type": item_type,
                "columns": columns_with_hints,
                "groups": board.get("groups", []),
            })

    return {"boards": matched[:limit], "total_matched": len(matched)}


def get_board_schema(board_id: str) -> Dict:
    """
    Get the column schema (field map) for a board.
    Returns column definitions like CSV headers.

    Also available via connector: get_connector().discover_board_schema(board_id)
    """
    query = """
    query ($boardId: [ID!]!) {
        boards(ids: $boardId) {
            id
            name
            columns {
                id
                title
                type
                settings_str
            }
            groups {
                id
                title
                color
            }
        }
    }
    """

    result = _make_request(query, {"boardId": [board_id]})

    if "error" in result:
        return result

    boards = result.get("data", {}).get("boards", [])
    if not boards:
        return {"error": f"Board {board_id} not found"}

    board = boards[0]

    # Parse settings for status/dropdown labels
    columns = []
    for col in board.get("columns", []):
        settings = {}
        if col.get("settings_str"):
            try:
                settings = json.loads(col["settings_str"])
            except:
                pass

        columns.append({
            "id": col["id"],
            "title": col["title"],
            "type": col["type"],
            "render_hint": MONDAY_TYPE_TO_RENDER_HINT.get(col["type"], "text"),
            "labels": settings.get("labels", {}),  # For status columns
            "options": settings.get("labels", {})   # For dropdown
        })

    return {
        "board_id": board["id"],
        "board_name": board["name"],
        "columns": columns,
        "groups": board.get("groups", [])
    }


# ============================================================
# ITEMS / DATA EXPORT
# ============================================================

def get_board_items(board_id: str, limit: int = 100) -> Dict:
    """
    Get all items from a board with their column values.
    Returns data similar to CSV export.

    For streaming large boards, use:
        connector = get_connector()
        for node in connector.traverse_hierarchy(board_id):
            process(node)
    """
    query = """
    query ($boardId: ID!, $limit: Int!) {
        boards(ids: [$boardId]) {
            name
            columns {
                id
                title
                type
            }
            items_page(limit: $limit) {
                cursor
                items {
                    id
                    name
                    group {
                        id
                        title
                    }
                    column_values {
                        id
                        type
                        text
                        value
                    }
                    created_at
                    updated_at
                }
            }
        }
    }
    """

    result = _make_request(query, {"boardId": board_id, "limit": limit})

    if "error" in result:
        return result

    boards = result.get("data", {}).get("boards", [])
    if not boards:
        return {"error": f"Board {board_id} not found"}

    board = boards[0]
    items_page = board.get("items_page", {})
    items = items_page.get("items", [])

    # Build column lookup with render hints
    columns = {}
    for col in board.get("columns", []):
        columns[col["id"]] = {
            **col,
            "render_hint": MONDAY_TYPE_TO_RENDER_HINT.get(col["type"], "text")
        }

    # Parse items like CSV rows
    rows = []
    for item in items:
        row = {
            "id": item["id"],
            "name": item["name"],
            "group": item.get("group", {}).get("title", ""),
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
        }

        # Add column values with render hints
        for cv in item.get("column_values", []):
            col_id = cv["id"]
            col_info = columns.get(col_id, {})
            col_title = col_info.get("title", col_id)

            # Use text for human-readable value
            row[col_title] = cv.get("text", "")
            row[f"__{col_id}"] = cv.get("value")  # Raw value for updates
            row[f"__{col_id}_render_hint"] = col_info.get("render_hint", "text")

        rows.append(row)

    # Build columns list with render hints
    column_list = []
    for col in board.get("columns", []):
        column_list.append({
            "id": col["id"],
            "title": col["title"],
            "type": col["type"],
            "render_hint": MONDAY_TYPE_TO_RENDER_HINT.get(col["type"], "text"),
        })

    return {
        "board_id": board_id,
        "board_name": board["name"],
        "columns": column_list,
        "column_titles": [col["title"] for col in board.get("columns", [])],
        "items": rows,
        "count": len(rows),
        "cursor": items_page.get("cursor")  # For pagination
    }


def export_board_as_csv(board_id: str, limit: int = 500) -> str:
    """
    Export board data as CSV string.
    """
    data = get_board_items(board_id, limit)
    
    if "error" in data:
        return f"Error: {data['error']}"
    
    if not data["items"]:
        return "No items found"
    
    # Get all column headers
    headers = ["id", "name", "group"] + data["columns"]
    
    lines = [",".join(headers)]
    
    for row in data["items"]:
        values = []
        for h in headers:
            v = str(row.get(h, "")).replace('"', '""')
            values.append(f'"{v}"')
        lines.append(",".join(values))
    
    return "\n".join(lines)


# ============================================================
# ITEM MUTATIONS (CREATE/UPDATE)
# ============================================================

def create_item(board_id: str, name: str, column_values: Optional[Dict] = None, group_id: Optional[str] = None) -> Dict:
    """
    Create a new item on a board.
    
    column_values format: {"column_id": value, ...}
    - Status: {"label": "Done"} or {"index": 1}
    - Date: {"date": "2026-01-15"}
    - Text: "Some text"
    - Numbers: 42
    - People: {"personsAndTeams": [{"id": 12345, "kind": "person"}]}
    """
    query = """
    mutation ($boardId: ID!, $itemName: String!, $groupId: String, $columnValues: JSON) {
        create_item(
            board_id: $boardId
            item_name: $itemName
            group_id: $groupId
            column_values: $columnValues
        ) {
            id
            name
        }
    }
    """
    
    variables = {
        "boardId": board_id,
        "itemName": name,
    }
    
    if group_id:
        variables["groupId"] = group_id
    
    if column_values:
        variables["columnValues"] = json.dumps(column_values)
    
    result = _make_request(query, variables)
    
    if "error" in result:
        return result
    
    created = result.get("data", {}).get("create_item", {})
    return {
        "success": True,
        "item_id": created.get("id"),
        "item_name": created.get("name")
    }


def update_item(board_id: str, item_id: str, column_values: Dict) -> Dict:
    """
    Update multiple column values on an item.
    
    column_values format: {"column_id": value, ...}
    """
    query = """
    mutation ($boardId: ID!, $itemId: ID!, $columnValues: JSON!) {
        change_multiple_column_values(
            board_id: $boardId
            item_id: $itemId
            column_values: $columnValues
        ) {
            id
            name
        }
    }
    """
    
    variables = {
        "boardId": board_id,
        "itemId": item_id,
        "columnValues": json.dumps(column_values)
    }
    
    result = _make_request(query, variables)
    
    if "error" in result:
        return result
    
    updated = result.get("data", {}).get("change_multiple_column_values", {})
    return {
        "success": True,
        "item_id": updated.get("id"),
        "item_name": updated.get("name")
    }


def add_update_to_item(item_id: str, body: str) -> Dict:
    """Add an update/comment to an item"""
    query = """
    mutation ($itemId: ID!, $body: String!) {
        create_update(item_id: $itemId, body: $body) {
            id
        }
    }
    """
    
    result = _make_request(query, {"itemId": item_id, "body": body})
    
    if "error" in result:
        return result
    
    return {
        "success": True,
        "update_id": result.get("data", {}).get("create_update", {}).get("id")
    }


# ============================================================
# HIGH-LEVEL FUNCTIONS
# ============================================================

def find_board_by_project(project_name: str) -> Dict:
    """Find a board by project name (partial match)"""
    result = search_boards(project_name, limit=10)
    
    if "error" in result:
        return result
    
    if not result["boards"]:
        return {"error": f"No board found matching: {project_name}"}
    
    # Return first match
    return {"board": result["boards"][0]}


def create_task_from_email(
    developer: str,
    project: str,
    task_name: str,
    description: str,
    due_date: Optional[str] = None,
    status: Optional[str] = None
) -> Dict:
    """
    Create a task on the appropriate board from email context.
    """
    # Search for board
    search_term = f"{developer} - {project}"
    board_result = search_boards(search_term, limit=5)
    
    if "error" in board_result:
        return board_result
    
    if not board_result["boards"]:
        return {"error": f"No board found for: {search_term}"}
    
    board = board_result["boards"][0]
    
    # Build column values
    column_values = {}
    
    # Find status column
    if status:
        for col in board.get("columns", []):
            if col["type"] == "status":
                column_values[col["id"]] = {"label": status}
                break
    
    # Find date column
    if due_date:
        for col in board.get("columns", []):
            if col["type"] == "date":
                column_values[col["id"]] = {"date": due_date}
                break
    
    # Create item
    result = create_item(
        board_id=board["id"],
        name=task_name,
        column_values=column_values if column_values else None
    )
    
    if "error" in result:
        return result
    
    # Add description as update
    if description and result.get("success"):
        add_update_to_item(result["item_id"], description)
    
    return {
        "success": True,
        "board_name": board["name"],
        "item_id": result["item_id"],
        "item_name": result["item_name"]
    }


def get_me() -> Dict:
    """Get current user info"""
    try:
        client = get_client()
        return {"data": {"me": client.get_me()}}
    except MondayClientError as e:
        return {"error": str(e)}


def get_items_for_project(project_name: str, limit: int = 10) -> Dict:
    """
    Get recent items from boards matching a project name.
    Used for suggesting which item to attach an email to.
    
    Returns:
        dict with boards and their items for selection
    """
    # First find matching boards
    board_result = search_boards(project_name, limit=5)
    
    if "error" in board_result:
        return board_result
    
    if not board_result["boards"]:
        return {"error": f"No boards found for project: {project_name}", "suggestions": []}
    
    suggestions = []
    
    for board in board_result["boards"][:3]:  # Max 3 boards
        items_result = get_board_items(board["id"], limit=limit)
        
        if "error" not in items_result:
            for item in items_result.get("items", [])[:limit]:
                suggestions.append({
                    "board_id": board["id"],
                    "board_name": board["name"],
                    "item_id": item["id"],
                    "item_name": item["name"],
                    "group": item.get("group", ""),
                })
    
    return {
        "project": project_name,
        "suggestions": suggestions,
        "count": len(suggestions)
    }


def format_email_for_monday(
    subject: str,
    sender: str,
    body: str,
    received_date: str = None,
    attachments: list = None
) -> str:
    """
    Format an email as markdown for Monday.com update.
    """
    lines = []
    
    # Header
    lines.append(f"### 📧 {subject}")
    lines.append("")
    lines.append(f"**From:** {sender}")
    if received_date:
        lines.append(f"**Date:** {received_date}")
    lines.append("")
    
    # Body (truncate if too long)
    body_preview = body[:2000] + "..." if len(body) > 2000 else body
    lines.append(body_preview)
    
    # Attachments
    if attachments:
        lines.append("")
        lines.append("**Attachments:**")
        for att in attachments:
            lines.append(f"- {att}")
    
    return "\n".join(lines)


def post_email_to_item(
    item_id: str,
    subject: str,
    sender: str,
    body: str,
    received_date: str = None,
    attachments: list = None
) -> Dict:
    """
    Post an email thread to a Monday.com item as an update.
    
    Args:
        item_id: The Monday.com item ID
        subject: Email subject
        sender: From address/name
        body: Email body text
        received_date: Optional date string
        attachments: Optional list of attachment filenames
    
    Returns:
        dict with success status and update ID
    """
    formatted = format_email_for_monday(
        subject=subject,
        sender=sender,
        body=body,
        received_date=received_date,
        attachments=attachments
    )
    
    return add_update_to_item(item_id, formatted)


# ============================================================
# NEW: CONNECTOR-BASED FUNCTIONS
# ============================================================

def discover_schema(board_id: str) -> Dict:
    """
    Discover board schema using the new MondayConnector.
    Returns a MondayBoardSchema with full column information.
    """
    try:
        connector = get_connector()
        schema = connector.discover_board_schema(board_id)
        return {
            "board_id": schema.board_id,
            "board_name": schema.board_name,
            "hierarchy_type": schema.hierarchy_type,
            "item_count": schema.item_count,
            "columns": [
                {
                    "id": col.id,
                    "title": col.title,
                    "type": col.type,
                    "render_hint": col.render_hint,
                    "labels": col.labels,
                }
                for col in schema.columns
            ],
            "groups": schema.groups,
        }
    except Exception as e:
        return {"error": str(e)}


def fetch_board_tree(board_id: str) -> Dict:
    """
    Fetch entire board as a hierarchical tree using MondayConnector.
    Returns the board with groups containing items containing subitems.
    """
    try:
        connector = get_connector()
        tree = connector.fetch_board(board_id)
        return _node_to_dict(tree)
    except Exception as e:
        return {"error": str(e)}


def _node_to_dict(node: MondayDataNode) -> Dict:
    """Convert a MondayDataNode tree to a serializable dict"""
    return {
        "type": node.type,
        "id": node.id,
        "name": node.name,
        "column_values": [
            {
                "id": cv.id,
                "title": cv.title,
                "type": cv.type,
                "text": cv.text,
                "value": cv.value,
                "render_hint": cv.render_hint,
            }
            for cv in node.column_values
        ],
        "children": [_node_to_dict(child) for child in node.children],
        "metadata": node.metadata,
    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    import os

    # Check for API key
    if not os.getenv('MONDAY_API_KEY'):
        print("ERROR: MONDAY_API_KEY environment variable not set")
        print("Set it with: export MONDAY_API_KEY='your-token-here'")
        exit(1)

    print("Testing Monday.com API (upgraded connector)...")

    # Test connection
    me = get_me()
    if "error" in me:
        print(f"Error: {me}")
        exit(1)

    user = me.get("data", {}).get("me", {})
    print(f"Connected as: {user.get('name')} ({user.get('email')})")

    # Search for a board
    print("\nSearching for 'Artesia'...")
    results = search_boards("Artesia", limit=5)
    if "error" in results:
        print(f"Error: {results}")
    else:
        print(f"Found {len(results['boards'])} boards:")
        for b in results["boards"]:
            print(f"  - {b['name']} (ID: {b['id']})")

        # Test new connector functions on first board
        if results["boards"]:
            board_id = results["boards"][0]["id"]

            # Test schema discovery
            print(f"\nDiscovering schema for board {board_id}...")
            schema = discover_schema(board_id)
            if "error" not in schema:
                print(f"  Board: {schema['board_name']}")
                print(f"  Columns: {len(schema['columns'])}")
                for col in schema['columns'][:5]:
                    print(f"    - {col['title']} ({col['type']} -> {col['render_hint']})")

            # Test items fetch
            print(f"\nFetching items from board {board_id}...")
            items = get_board_items(board_id, limit=5)
            if "error" in items:
                print(f"  Error: {items}")
            else:
                print(f"  Found {items['count']} items")
                for item in items["items"][:3]:
                    print(f"    - {item['name']}")

            # Test hierarchy traversal
            print(f"\nTraversing hierarchy for board {board_id}...")
            try:
                connector = get_connector()
                node_count = 0
                for node in connector.traverse_hierarchy(board_id):
                    node_count += 1
                    if node_count <= 5:
                        print(f"    [{node.type}] {node.name}")
                print(f"  Total nodes: {node_count}")
            except Exception as e:
                print(f"  Error traversing: {e}")

    print("\nDone!")
