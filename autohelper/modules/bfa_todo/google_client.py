"""Thin httpx wrapper for Google Docs/Sheets API calls.

Uses the OAuth tokens stored in config.json via ConfigStore.
Handles token refresh transparently.
"""

from __future__ import annotations

import httpx

from autohelper.config import get_settings, reset_settings
from autohelper.config.store import ConfigStore
from autohelper.shared.logging import get_logger

logger = get_logger(__name__)

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
DOCS_API = "https://docs.googleapis.com/v1/documents"
SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"


class GoogleClientError(Exception):
    """Raised when a Google API call fails."""

    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


class GoogleDocsClient:
    """Thin async wrapper for Google Docs/Sheets API."""

    def __init__(self) -> None:
        self._store = ConfigStore()

    def _get_token(self) -> str:
        """Read access token from config.json."""
        cfg = self._store.load()
        token = cfg.get("google_token", "")
        if not token:
            raise GoogleClientError("No Google access token. Connect Google in Settings.", 401)
        return token

    def _get_refresh_token(self) -> str:
        cfg = self._store.load()
        return cfg.get("google_refresh_token", "")

    async def _refresh_access_token(self) -> str:
        """Use refresh token to get a new access token."""
        refresh_token = self._get_refresh_token()
        if not refresh_token:
            raise GoogleClientError("No refresh token available. Re-connect Google in Settings.", 401)

        settings = get_settings()
        client_id = getattr(settings, "google_client_id", "")
        client_secret = getattr(settings, "google_client_secret", "")

        if not client_id or not client_secret:
            raise GoogleClientError("Google OAuth credentials not configured.", 401)

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(GOOGLE_TOKEN_URL, data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            })
            if resp.status_code != 200:
                raise GoogleClientError(f"Token refresh failed: {resp.status_code} {resp.text}", resp.status_code)

            tokens = resp.json()
            new_token = tokens.get("access_token", "")
            if not new_token:
                raise GoogleClientError("Token refresh returned no access_token.", 502)

            # Persist the new token
            cfg = self._store.load()
            cfg["google_token"] = new_token
            self._store.save(cfg)
            reset_settings()
            logger.info("Google access token refreshed")
            return new_token

    async def _request(self, method: str, url: str, **kwargs) -> dict:
        """Make an authenticated request, refreshing token on 401."""
        token = self._get_token()

        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {"Authorization": f"Bearer {token}"}
            resp = await client.request(method, url, headers=headers, **kwargs)

            if resp.status_code == 401:
                # Try refresh
                token = await self._refresh_access_token()
                headers = {"Authorization": f"Bearer {token}"}
                resp = await client.request(method, url, headers=headers, **kwargs)

            if resp.status_code >= 400:
                raise GoogleClientError(
                    f"Google API error: {resp.status_code} {resp.text[:200]}",
                    resp.status_code,
                )
            return resp.json()

    async def get_document(self, doc_id: str) -> dict:
        """GET documents/{doc_id}"""
        return await self._request("GET", f"{DOCS_API}/{doc_id}")

    async def batch_update(self, doc_id: str, requests: list) -> dict:
        """POST documents/{doc_id}:batchUpdate"""
        return await self._request(
            "POST",
            f"{DOCS_API}/{doc_id}:batchUpdate",
            json={"requests": requests},
        )
