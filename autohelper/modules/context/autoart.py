"""
AutoArt API Client for AutoHelper Context Layer

Fetches project/record definitions from the AutoArt backend.
Provides a fallback context source alongside Monday.com.
"""

import logging
from dataclasses import dataclass
from typing import Any, cast

import requests

logger = logging.getLogger(__name__)


@dataclass
class AutoArtClientConfig:
    """Configuration for AutoArt client"""

    api_url: str = "http://localhost:3000"
    link_key: str | None = None


class AutoArtClientError(Exception):
    """Error from AutoArt API"""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class AutoArtClient:
    """
    AutoArt REST API Client for AutoHelper

    Fetches project/entity data from the local AutoArt backend
    for context-aware email processing.

    Usage:
        from autohelper.config.settings import get_settings
        settings = get_settings()
        client = AutoArtClient(
            api_url=settings.autoart_api_url,
            link_key=settings.autoart_link_key or None,
        )
        projects = client.fetch_projects()
    """

    def __init__(
        self,
        api_url: str | None = None,
        link_key: str | None = None,
    ):
        if api_url is None:
            api_url = "http://localhost:3001"
        self.api_url = api_url.rstrip("/")
        self.link_key = link_key
        self._cached_projects: list[dict[str, Any]] | None = None
        self._cached_developers: list[str] | None = None

    def _get_headers(self) -> dict[str, str]:
        """Build request headers with optional link key."""
        headers = {"Content-Type": "application/json"}
        if self.link_key:
            headers["X-AutoHelper-Key"] = self.link_key
        return headers

    def _request(
        self, method: str, endpoint: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Make a request to the AutoArt API."""
        url = f"{self.api_url}{endpoint}"
        try:
            response = requests.request(
                method=method, url=url, headers=self._get_headers(), params=params, timeout=10
            )
        except requests.RequestException as e:
            logger.error(f"AutoArt API request failed: {e}")
            raise AutoArtClientError(f"Request failed: {e}") from e

        if response.status_code != 200:
            raise AutoArtClientError(
                f"HTTP {response.status_code}: {response.text}", status_code=response.status_code
            )

        return cast(dict[str, Any], response.json())

    def test_connection(self) -> bool:
        """Test if the AutoArt API is reachable."""
        try:
            self._request("GET", "/health")
            return True
        except AutoArtClientError:
            return False

    def fetch_projects(self, force_refresh: bool = False) -> list[dict[str, Any]]:
        """
        Fetch all projects/records from AutoArt.

        Returns list of dicts with:
            - id: Record ID
            - name: Record name (project name)
            - definition: Definition type (e.g., "Project", "Task")
            - parent: Parent record ID if applicable
        """
        if self._cached_projects and not force_refresh:
            return self._cached_projects

        try:
            result = self._request("GET", "/api/records", {"definitionType": "Project"})
            records = result.get("data", []) if isinstance(result, dict) else result
            self._cached_projects = [
                {
                    "id": r.get("id"),
                    "name": r.get("name") or r.get("title", ""),
                    "definition": r.get("definitionType", "Unknown"),
                    "parent": r.get("parentId"),
                }
                for r in records
            ]
            return self._cached_projects
        except AutoArtClientError as e:
            logger.warning(f"Failed to fetch projects from AutoArt: {e}")
            return []

    def fetch_developers(self, force_refresh: bool = False) -> list[str]:
        """
        Fetch known developer names from AutoArt.

        These can be extracted from project naming conventions
        or a dedicated "Developer" definition type.
        """
        if self._cached_developers and not force_refresh:
            return self._cached_developers

        try:
            # Try to fetch records of type "Developer" or "Client"
            result = self._request("GET", "/api/records", {"definitionType": "Developer"})
            records = result.get("data", []) if isinstance(result, dict) else result

            if not records:
                # Fallback: extract from project names (e.g., "Developer - Project")
                projects = self.fetch_projects(force_refresh)
                developers = set()
                for project in projects:
                    name = project.get("name", "")
                    if " - " in name:
                        dev = name.split(" - ")[0].strip()
                        if dev:
                            developers.add(dev)
                self._cached_developers = list(developers)
            else:
                self._cached_developers = [
                    r.get("name") or r.get("title", "")
                    for r in records
                    if r.get("name") or r.get("title")
                ]

            return self._cached_developers
        except AutoArtClientError as e:
            logger.warning(f"Failed to fetch developers from AutoArt: {e}")
            return []

    def get_linked_connection_status(self) -> dict[str, Any] | None:
        """Fetch OAuth connection statuses from autoart for the linked user."""
        if not self.link_key:
            return None
        try:
            return self._request("GET", "/api/connections/linked-status")
        except AutoArtClientError:
            return None

    def clear_cache(self) -> None:
        """Clear cached data."""
        self._cached_projects = None
        self._cached_developers = None

    def verify_key(self) -> bool:
        """Check if the link key is recognized by the backend (no Monday dependency)."""
        try:
            response = requests.get(
                f"{self.api_url}/api/connections/autohelper/verify",
                headers=self._get_headers(),
                timeout=10,
            )
            return response.status_code == 200
        except requests.RequestException:
            return False

    # =========================================================================
    # GARBAGE COLLECTION
    # =========================================================================

    def delete_stale_import_sessions(
        self, older_than_days: int = 7
    ) -> tuple[int, list[str]]:
        """
        Delete stale import sessions from the backend.

        Args:
            older_than_days: Delete sessions older than this many days

        Returns:
            Tuple of (deleted_count, session_ids)
        """
        try:
            response = requests.delete(
                f"{self.api_url}/api/imports/sessions/stale",
                params={"older_than_days": older_than_days},
                headers=self._get_headers(),
                timeout=30,
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("deleted_count", 0), result.get("session_ids", [])
            else:
                logger.warning(
                    f"Failed to delete stale import sessions: {response.status_code}"
                )
                return 0, []

        except requests.RequestException as e:
            logger.error(f"Error deleting stale import sessions: {e}")
            return 0, []

    def delete_stale_export_sessions(
        self, older_than_days: int = 7
    ) -> tuple[int, list[str]]:
        """
        Delete stale export sessions from the backend.

        Args:
            older_than_days: Delete sessions older than this many days

        Returns:
            Tuple of (deleted_count, session_ids)
        """
        try:
            response = requests.delete(
                f"{self.api_url}/api/exports/sessions/stale",
                params={"older_than_days": older_than_days},
                headers=self._get_headers(),
                timeout=30,
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("deleted_count", 0), result.get("session_ids", [])
            else:
                logger.warning(
                    f"Failed to delete stale export sessions: {response.status_code}"
                )
                return 0, []

        except requests.RequestException as e:
            logger.error(f"Error deleting stale export sessions: {e}")
            return 0, []

    def get_gc_stats(self, retention_days: int = 7) -> dict[str, Any] | None:
        """
        Get garbage collection stats from the backend.

        Args:
            retention_days: Retention period for stats calculation

        Returns:
            Stats dict or None on failure
        """
        try:
            response = requests.get(
                f"{self.api_url}/api/gc/stats",
                params={"retention_days": retention_days},
                headers=self._get_headers(),
                timeout=10,
            )

            if response.status_code == 200:
                result: dict[str, Any] = response.json()
                return result
            else:
                logger.warning(f"Failed to get GC stats: {response.status_code}")
                return None

        except requests.RequestException as e:
            logger.error(f"Error getting GC stats: {e}")
            return None
