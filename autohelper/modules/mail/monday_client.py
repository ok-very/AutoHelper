"""
DEPRECATED: This module has been ported to AutoHelper.
Please use `autohelper.modules.context.monday` instead.

Monday.com GraphQL Client
"""

import warnings
warnings.warn(
    "This module is deprecated. Use `autohelper.modules.context.monday` instead.",
    DeprecationWarning,
    stacklevel=2
)

import os
import requests
from typing import TypeVar, Optional, Any
from dataclasses import dataclass


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
    Monday.com GraphQL API Client

    Usage:
        client = MondayClient()  # Uses MONDAY_API_KEY env var
        client = MondayClient(token="your-token")  # Explicit token

        result = client.query('''
            query { me { id name email } }
        ''')
    """

    def __init__(
        self,
        token: str | None = None,
        api_version: str = "2024-10"
    ):
        self.token = token or os.getenv('MONDAY_API_KEY')
        if not self.token:
            raise ValueError(
                "Monday API token required. "
                "Pass token parameter or set MONDAY_API_KEY environment variable."
            )

        self.api_url = "https://api.monday.com/v2"
        self.api_version = api_version

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

    def mutate(
        self,
        mutation: str,
        variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Execute a GraphQL mutation against the Monday.com API.

        This is an alias for query() since GraphQL doesn't distinguish
        at the transport level.
        """
        return self.query(mutation, variables)

    def get_me(self) -> dict[str, Any]:
        """Get current user info - useful for testing connection"""
        result = self.query("""
            query {
                me {
                    id
                    name
                    email
                }
            }
        """)
        return result.get("me", {})


# Module-level convenience for backward compatibility
_default_client: MondayClient | None = None


def get_client() -> MondayClient:
    """Get or create the default Monday client instance"""
    global _default_client
    if _default_client is None:
        _default_client = MondayClient()
    return _default_client


def reset_client():
    """Reset the default client (useful for testing)"""
    global _default_client
    _default_client = None
