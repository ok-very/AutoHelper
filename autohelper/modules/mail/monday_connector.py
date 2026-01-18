"""
DEPRECATED: This module has been ported to AutoHelper.
Please use `autohelper.modules.context.monday` instead.

Monday.com Connector
"""

import warnings
warnings.warn(
    "This module is deprecated. Use `autohelper.modules.context.monday` instead.",
    DeprecationWarning,
    stacklevel=2
)

import json
from typing import Any, Generator, Literal
from dataclasses import dataclass, field

from .monday_client import MondayClient


# ============================================================================
# RENDER HINT MAPPING
# ============================================================================

MONDAY_TYPE_TO_RENDER_HINT: dict[str, str] = {
    # Core types
    'name': 'text',
    'text': 'text',
    'long_text': 'longtext',
    'status': 'status',
    'date': 'date',
    'people': 'person',
    'numbers': 'number',

    # Selection types
    'dropdown': 'select',
    'color_picker': 'select',

    # Rich types
    'timeline': 'timeline',
    'doc': 'doc',
    'file': 'file',
    'link': 'url',
    'email': 'email',
    'phone': 'phone',
    'checkbox': 'checkbox',

    # Relation types
    'board_relation': 'relation',
    'mirror': 'mirror',
    'subtasks': 'subtasks',

    # Misc
    'country': 'text',
    'location': 'text',
    'rating': 'number',
    'auto_number': 'number',
    'formula': 'text',
    'tags': 'tags',
    'week': 'date',
    'hour': 'text',
    'world_clock': 'text',
    'dependency': 'relation',
}


# ============================================================================
# TYPES
# ============================================================================

@dataclass
class MondayColumnSchema:
    """Schema for a Monday.com column"""
    id: str
    title: str
    type: str
    settings: dict[str, Any] | None = None
    sample_values: list[str] = field(default_factory=list)

    @property
    def render_hint(self) -> str:
        """Get the render hint for this column type"""
        return MONDAY_TYPE_TO_RENDER_HINT.get(self.type, 'text')

    @property
    def labels(self) -> dict[str, str]:
        """Get status/dropdown labels if available"""
        if self.settings and 'labels' in self.settings:
            return self.settings['labels']
        return {}


@dataclass
class MondayBoardSchema:
    """Schema for a Monday.com board"""
    board_id: str
    board_name: str
    columns: list[MondayColumnSchema]
    groups: list[dict[str, str]]  # {id, title, color}
    hierarchy_type: Literal['classic', 'multi_level']
    item_count: int


@dataclass
class MondayColumnValue:
    """Normalized column value with render hint"""
    id: str
    title: str
    type: str
    text: str | None
    value: Any
    render_hint: str


@dataclass
class MondayDataNode:
    """
    Normalized node in the Monday.com hierarchy.
    Can represent: board, group, item, or subitem.
    """
    type: Literal['board', 'group', 'item', 'subitem']
    id: str
    name: str
    column_values: list[MondayColumnValue] = field(default_factory=list)
    children: list['MondayDataNode'] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    # Note: parent reference omitted to avoid circular references in serialization


# ============================================================================
# GRAPHQL QUERIES
# ============================================================================

BOARD_SCHEMA_QUERY = """
query DiscoverSchema($boardId: ID!) {
    boards(ids: [$boardId]) {
        id
        name
        hierarchy_type
        items_count
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

BOARD_ITEMS_QUERY = """
query GetBoardItems($boardId: ID!, $cursor: String, $limit: Int!) {
    boards(ids: [$boardId]) {
        items_page(limit: $limit, cursor: $cursor) {
            cursor
            items {
                id
                name
                group {
                    id
                    title
                }
                created_at
                updated_at
                creator {
                    id
                    name
                }
                state
                column_values {
                    id
                    text
                    value
                    type
                }
                subitems {
                    id
                    name
                    created_at
                    updated_at
                    column_values {
                        id
                        text
                        value
                        type
                    }
                }
            }
        }
    }
}
"""


# ============================================================================
# CONNECTOR CLASS
# ============================================================================

class MondayConnector:
    """
    Connector for traversing Monday.com board hierarchy.

    Usage:
        client = MondayClient()
        connector = MondayConnector(client)

        # Get board schema
        schema = connector.discover_board_schema("123456789")

        # Fetch entire board as tree
        board = connector.fetch_board("123456789")

        # Stream nodes for large boards
        for node in connector.traverse_hierarchy("123456789"):
            print(node.name)
    """

    def __init__(self, client: MondayClient):
        self.client = client

    def discover_board_schema(self, board_id: str) -> MondayBoardSchema:
        """
        Discover board schema without fetching all items.
        Use this for initial column mapping and entity inference.
        """
        data = self.client.query(BOARD_SCHEMA_QUERY, {"boardId": board_id})

        boards = data.get("boards", [])
        if not boards:
            raise ValueError(f"Board {board_id} not found")

        board = boards[0]

        columns = []
        for col in board.get("columns", []):
            settings = None
            if col.get("settings_str"):
                try:
                    settings = json.loads(col["settings_str"])
                except json.JSONDecodeError:
                    pass

            columns.append(MondayColumnSchema(
                id=col["id"],
                title=col["title"],
                type=col["type"],
                settings=settings,
            ))

        return MondayBoardSchema(
            board_id=board["id"],
            board_name=board["name"],
            hierarchy_type=board.get("hierarchy_type", "classic"),
            item_count=board.get("items_count", 0),
            groups=board.get("groups", []),
            columns=columns,
        )

    def fetch_board(self, board_id: str) -> MondayDataNode:
        """
        Fetch entire board as a tree structure.
        For smaller boards or when you need the full tree.
        """
        schema = self.discover_board_schema(board_id)

        board_node = MondayDataNode(
            type='board',
            id=schema.board_id,
            name=schema.board_name,
            metadata={},
        )

        # Create group nodes
        group_map: dict[str, MondayDataNode] = {}
        for group in schema.groups:
            group_node = MondayDataNode(
                type='group',
                id=group["id"],
                name=group["title"],
                metadata={
                    "group_id": group["id"],
                    "group_title": group["title"],
                    "color": group.get("color"),
                },
            )
            group_map[group["id"]] = group_node
            board_node.children.append(group_node)

        # Fetch all items with pagination
        cursor: str | None = None
        page_size = 100

        while True:
            page = self._fetch_items_page(board_id, cursor, page_size)
            cursor = page["cursor"]

            for item in page["items"]:
                item_node = self._create_item_node(item, schema.columns)

                # Find parent group
                group_id = item.get("group", {}).get("id")
                parent_group = group_map.get(group_id) if group_id else None

                if parent_group:
                    item_node.metadata["group_id"] = group_id
                    item_node.metadata["group_title"] = item.get("group", {}).get("title")
                    parent_group.children.append(item_node)
                else:
                    # Item without group - attach directly to board
                    board_node.children.append(item_node)

                # Add subitems
                for subitem in item.get("subitems", []):
                    subitem_node = self._create_item_node(
                        subitem, schema.columns, node_type='subitem'
                    )
                    subitem_node.metadata["parent_item_id"] = item["id"]
                    item_node.children.append(subitem_node)

            if not cursor:
                break

        return board_node

    def traverse_hierarchy(
        self,
        board_id: str,
        include_subitems: bool = True
    ) -> Generator[MondayDataNode, None, None]:
        """
        Stream items from a board using a generator.
        Memory-efficient for large boards.
        """
        schema = self.discover_board_schema(board_id)

        # Yield board node first
        yield MondayDataNode(
            type='board',
            id=schema.board_id,
            name=schema.board_name,
            metadata={},
        )

        # Yield group nodes
        for group in schema.groups:
            yield MondayDataNode(
                type='group',
                id=group["id"],
                name=group["title"],
                metadata={
                    "group_id": group["id"],
                    "group_title": group["title"],
                    "color": group.get("color"),
                },
            )

        # Stream items with pagination
        cursor: str | None = None
        page_size = 100

        while True:
            page = self._fetch_items_page(board_id, cursor, page_size)
            cursor = page["cursor"]

            for item in page["items"]:
                item_node = self._create_item_node(item, schema.columns)
                item_node.metadata["group_id"] = item.get("group", {}).get("id")
                item_node.metadata["group_title"] = item.get("group", {}).get("title")

                yield item_node

                # Yield subitems with parent reference
                if include_subitems:
                    for subitem in item.get("subitems", []):
                        subitem_node = self._create_item_node(
                            subitem, schema.columns, node_type='subitem'
                        )
                        subitem_node.metadata["parent_item_id"] = item["id"]
                        yield subitem_node

            if not cursor:
                break

    # ============================================================================
    # PRIVATE HELPERS
    # ============================================================================

    def _fetch_items_page(
        self,
        board_id: str,
        cursor: str | None,
        limit: int
    ) -> dict[str, Any]:
        """Fetch a single page of items"""
        data = self.client.query(BOARD_ITEMS_QUERY, {
            "boardId": board_id,
            "cursor": cursor,
            "limit": limit,
        })

        boards = data.get("boards", [])
        if not boards:
            return {"cursor": None, "items": []}

        items_page = boards[0].get("items_page", {})
        return {
            "cursor": items_page.get("cursor"),
            "items": items_page.get("items", []),
        }

    def _create_item_node(
        self,
        item: dict[str, Any],
        column_schema: list[MondayColumnSchema],
        node_type: Literal['item', 'subitem'] = 'item'
    ) -> MondayDataNode:
        """Create a MondayDataNode from a raw item"""
        # Map column values with titles and render hints from schema
        column_map = {col.id: col for col in column_schema}

        column_values = []
        for cv in item.get("column_values", []):
            schema = column_map.get(cv["id"])

            # Parse value JSON if present
            parsed_value = None
            if cv.get("value"):
                try:
                    parsed_value = json.loads(cv["value"])
                except (json.JSONDecodeError, TypeError):
                    parsed_value = cv["value"]

            column_values.append(MondayColumnValue(
                id=cv["id"],
                title=schema.title if schema else cv["id"],
                type=cv.get("type") or (schema.type if schema else "unknown"),
                text=cv.get("text"),
                value=parsed_value,
                render_hint=MONDAY_TYPE_TO_RENDER_HINT.get(
                    cv.get("type") or (schema.type if schema else ""),
                    'text'
                ),
            ))

        return MondayDataNode(
            type=node_type,
            id=item["id"],
            name=item["name"],
            column_values=column_values,
            metadata={
                "creator": item.get("creator"),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "state": item.get("state"),
            },
        )


# ============================================================================
# MODULE-LEVEL CONVENIENCE
# ============================================================================

def get_connector(client: MondayClient | None = None) -> MondayConnector:
    """Get a connector instance, creating a default client if needed"""
    from .monday_client import get_client
    return MondayConnector(client or get_client())
