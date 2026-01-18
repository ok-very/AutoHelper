"""
Monday.com GraphQL Client for AutoHelper Context Layer

Adapted from automail/scripts/monday_client.py for integration with AutoHelper.
Provides consistent API access with settings-based configuration.
"""

import requests
from typing import TypeVar, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class MondayClientConfig:
    """Configuration for Monday.com client"""
    token: str
    api_version: str = "2024-10"
    api_url: str = "https://api.monday.com/v2"


class MondayClientError(Exception):
    """Error from Monday.com API"""
    def __init__(
        self,
        message: str,
        errors: list[dict] | None = None,
        status_code: int | None = None
    ):
        super().__init__(message)
        self.errors = errors
        self.status_code = status_code


T = TypeVar('T')


class MondayClient:
    """
    Monday.com GraphQL API Client for AutoHelper

    Usage:
        from autohelper.config.settings import get_settings
        settings = get_settings()
        client = MondayClient(token=settings.monday_api_token)

        result = client.query('''
            query { me { id name email } }
        ''')
    """

    def __init__(
        self,
        token: str,
        api_version: str = "2024-10"
    ):
        if not token:
            raise ValueError(
                "Monday API token required. "
                "Configure via Settings or AUTOHELPER_MONDAY_API_TOKEN env var."
            )

        self.token = token
        self.api_url = "https://api.monday.com/v2"
        self.api_version = api_version
        self._cached_me: dict[str, Any] | None = None

    def query(
        self,
        query: str,
        variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Execute a GraphQL query against the Monday.com API.

        Args:
            query: GraphQL query string
            variables: Optional variables for the query

        Returns:
            The 'data' portion of the GraphQL response

        Raises:
            MondayClientError: If the API returns an error
        """
        headers = {
            "Authorization": self.token,
            "Content-Type": "application/json",
            "API-Version": self.api_version
        }

        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=30
            )
        except requests.RequestException as e:
            logger.error(f"Monday API request failed: {e}")
            raise MondayClientError(f"Request failed: {e}") from e

        if response.status_code != 200:
            raise MondayClientError(
                f"HTTP {response.status_code}: {response.text}",
                status_code=response.status_code
            )

        result = response.json()

        if "errors" in result:
            errors = result["errors"]
            messages = [e.get("message", "Unknown error") for e in errors]
            raise MondayClientError(
                "; ".join(messages),
                errors=errors,
                status_code=response.status_code
            )

        return result.get("data", {})

    def get_me(self) -> dict[str, Any]:
        """Get current user info - useful for testing connection"""
        if self._cached_me:
            return self._cached_me
        
        result = self.query("""
            query {
                me {
                    id
                    name
                    email
                }
            }
        """)
        self._cached_me = result.get("me", {})
        return self._cached_me

    def test_connection(self) -> bool:
        """Test if the API token is valid. Returns True if successful."""
        try:
            self.get_me()
            return True
        except MondayClientError:
            return False

    def fetch_boards_summary(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        Fetch a summary of all boards (name, id) for context matching.
        Returns list of {id, name, developer, project} dicts.
        """
        query = """
        query ($limit: Int!) {
            boards(limit: $limit, state: active) {
                id
                name
            }
        }
        """
        result = self.query(query, {"limit": limit})
        boards = result.get("boards", [])
        
        parsed = []
        for board in boards:
            developer, project, item_type = self._parse_board_name(board["name"])
            parsed.append({
                "id": board["id"],
                "name": board["name"],
                "developer": developer,
                "project": project,
                "item_type": item_type,
            })
        return parsed

    def fetch_groups_for_board(self, board_id: str) -> list[dict[str, Any]]:
        """Fetch groups for a specific board."""
        query = """
        query ($boardId: [ID!]!) {
            boards(ids: $boardId) {
                groups {
                    id
                    title
                    color
                }
            }
        }
        """
        result = self.query(query, {"boardId": [board_id]})
        boards = result.get("boards", [])
        if not boards:
            return []
        return boards[0].get("groups", [])

    @staticmethod
    def _parse_board_name(name: str) -> tuple[str, str, str]:
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
