"""
AutoArt API Client for AutoHelper Context Layer

Fetches project/record definitions from the AutoArt backend.
Provides a fallback context source alongside Monday.com.
"""

import requests
from typing import Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class AutoArtClientConfig:
    """Configuration for AutoArt client"""
    api_url: str = "http://localhost:3000"
    api_key: str | None = None


class AutoArtClientError(Exception):
    """Error from AutoArt API"""
    def __init__(
        self,
        message: str,
        status_code: int | None = None
    ):
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
            api_key=settings.autoart_api_key
        )
        projects = client.fetch_projects()
    """

    def __init__(
        self,
        api_url: str = "http://localhost:3000",
        api_key: str | None = None,
        session_id: str | None = None
    ):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.session_id = session_id
        self._cached_projects: list[dict[str, Any]] | None = None
        self._cached_developers: list[str] | None = None

    def _get_headers(self) -> dict[str, str]:
        """Build request headers with optional API key and session ID."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.session_id:
            headers["X-AutoHelper-Session"] = self.session_id
        return headers

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Make a request to the AutoArt API."""
        url = f"{self.api_url}{endpoint}"
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self._get_headers(),
                params=params,
                timeout=10
            )
        except requests.RequestException as e:
            logger.error(f"AutoArt API request failed: {e}")
            raise AutoArtClientError(f"Request failed: {e}") from e

        if response.status_code != 200:
            raise AutoArtClientError(
                f"HTTP {response.status_code}: {response.text}",
                status_code=response.status_code
            )

        return response.json()

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
    
    def clear_cache(self) -> None:
        """Clear cached data."""
        self._cached_projects = None
        self._cached_developers = None
    
    # =========================================================================
    # PAIRING & CREDENTIAL PROXYING
    # =========================================================================
    
    def pair_with_code(self, code: str, instance_name: str = "AutoHelper") -> str | None:
        """
        Exchange a pairing code for a session ID.
        
        Args:
            code: 6-digit pairing code from AutoArt
            instance_name: Name to identify this AutoHelper instance
            
        Returns:
            Session ID on success, None on failure
        """
        try:
            response = requests.post(
                f"{self.api_url}/api/connections/autohelper/handshake",
                json={"code": code, "instanceName": instance_name},
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                session_id = result.get("sessionId")
                logger.info(f"Paired with AutoArt, session: {session_id[:8]}...")
                return session_id
            else:
                logger.warning(f"Pairing failed: {response.status_code} - {response.text}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Pairing request failed: {e}")
            return None
    
    def get_monday_token(self, session_id: str) -> str | None:
        """
        Fetch Monday API token from AutoArt using session credentials.
        
        This makes AutoArt the single source of truth for API tokens,
        eliminating the need to store the Monday key locally.
        
        Args:
            session_id: Valid session ID from pairing
            
        Returns:
            Monday API token on success, None on failure
        """
        try:
            response = requests.get(
                f"{self.api_url}/api/connections/autohelper/credentials",
                headers={
                    "X-AutoHelper-Session": session_id,
                    "Content-Type": "application/json"
                },
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                token = result.get("monday_api_token")
                if token:
                    logger.debug("Retrieved Monday token from AutoArt")
                    return token
                    
            logger.warning(f"Failed to get Monday token: {response.status_code}")
            return None
            
        except requests.RequestException as e:
            logger.error(f"Credential fetch failed: {e}")
            return None
    
    def verify_session(self, session_id: str) -> bool:
        """
        Verify that a session ID is still valid.
        
        Args:
            session_id: Session ID to verify
            
        Returns:
            True if session is valid, False otherwise
        """
        # The credentials endpoint will fail if session is invalid
        return self.get_monday_token(session_id) is not None

