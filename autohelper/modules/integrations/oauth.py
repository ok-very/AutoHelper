"""Generic OAuth 2.0 routes for Google Workspace and Monday.com.

Uses the same popup + postMessage pattern as the ClickUp OAuth flow.
Tokens are stored in config.json via ConfigStore.
"""

from __future__ import annotations

import secrets
import time
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from autohelper.config import get_settings, reset_settings
from autohelper.config.store import ConfigStore
from autohelper.shared.logging import get_logger

logger = get_logger(__name__)

# ── State store (shared across providers, 10-minute TTL) ─────────────

_oauth_states: dict[str, tuple[str, float]] = {}  # state -> (provider, expiry)
_STATE_TTL = 600

router = APIRouter(tags=["oauth"])


def _clean_expired() -> None:
    now = time.time()
    expired = [k for k, (_, exp) in _oauth_states.items() if exp < now]
    for k in expired:
        del _oauth_states[k]


def _popup_html(ok: bool, provider: str, error: str = "") -> str:
    msg_type = f"{provider}-oauth"
    if ok:
        return (
            f"<html><body><h2>Connected to {provider.title()}</h2>"
            f"<p>You can close this window.</p>"
            f"<script>window.opener?.postMessage({{type:'{msg_type}',ok:true}},'*');"
            f"setTimeout(()=>window.close(),1000)</script></body></html>"
        )
    return (
        f"<html><body><h2>Authorization failed</h2>"
        f"<p>{error}</p>"
        f"<script>window.opener?.postMessage({{type:'{msg_type}',ok:false,error:'{error}'}},'*');"
        f"window.close()</script></body></html>"
    )


# ── Google Workspace ─────────────────────────────────────────────────

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
]


@router.get("/google/auth")
async def google_auth() -> dict[str, Any]:
    """Initiate Google OAuth flow."""
    settings = get_settings()
    client_id = getattr(settings, "google_client_id", "")
    redirect_uri = getattr(settings, "google_redirect_uri", "")
    if not client_id:
        raise HTTPException(400, "GOOGLE_CLIENT_ID not configured")

    _clean_expired()
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = ("google", time.time() + _STATE_TTL)

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return {"url": f"{GOOGLE_AUTH_URL}?{urlencode(params)}", "state": state}


@router.get("/google/callback", response_class=HTMLResponse)
async def google_callback(
    code: str = Query(...),
    state: str = Query(""),
) -> HTMLResponse:
    """Handle Google OAuth callback."""
    entry = _oauth_states.pop(state, None)
    if not state or entry is None or entry[1] < time.time():
        return HTMLResponse(_popup_html(False, "google", "invalid_state"), 400)

    settings = get_settings()
    client_id = getattr(settings, "google_client_id", "")
    client_secret = getattr(settings, "google_client_secret", "")
    redirect_uri = getattr(settings, "google_redirect_uri", "")

    if not client_id or not client_secret:
        return HTMLResponse(_popup_html(False, "google", "no_credentials"), 500)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(GOOGLE_TOKEN_URL, data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            })
            resp.raise_for_status()
            tokens = resp.json()

            # Fetch user info for display
            userinfo_resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            userinfo = userinfo_resp.json() if userinfo_resp.status_code == 200 else {}
    except Exception as exc:
        logger.error("Google token exchange failed: %s", exc)
        return HTMLResponse(_popup_html(False, "google", "token_exchange_failed"), 502)

    access_token = tokens.get("access_token")
    if not access_token:
        return HTMLResponse(_popup_html(False, "google", "no_token"), 502)

    store = ConfigStore()
    cfg = store.load()
    cfg["google_token"] = access_token
    cfg["google_refresh_token"] = tokens.get("refresh_token", cfg.get("google_refresh_token", ""))
    cfg["google_account_name"] = userinfo.get("email", "")
    store.save(cfg)
    reset_settings()

    logger.info("Google OAuth token acquired for %s", userinfo.get("email", "unknown"))
    return HTMLResponse(_popup_html(True, "google"))


# ── Monday.com ───────────────────────────────────────────────────────

MONDAY_AUTH_URL = "https://auth.monday.com/oauth2/authorize"
MONDAY_TOKEN_URL = "https://auth.monday.com/oauth2/token"


@router.get("/monday/auth")
async def monday_auth() -> dict[str, Any]:
    """Initiate Monday.com OAuth flow."""
    settings = get_settings()
    client_id = getattr(settings, "monday_client_id", "")
    redirect_uri = getattr(settings, "monday_redirect_uri", "")
    if not client_id:
        raise HTTPException(400, "MONDAY_CLIENT_ID not configured")

    _clean_expired()
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = ("monday", time.time() + _STATE_TTL)

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return {"url": f"{MONDAY_AUTH_URL}?{urlencode(params)}", "state": state}


@router.get("/monday/callback", response_class=HTMLResponse)
async def monday_callback(
    code: str = Query(...),
    state: str = Query(""),
) -> HTMLResponse:
    """Handle Monday.com OAuth callback."""
    entry = _oauth_states.pop(state, None)
    if not state or entry is None or entry[1] < time.time():
        return HTMLResponse(_popup_html(False, "monday", "invalid_state"), 400)

    settings = get_settings()
    client_id = getattr(settings, "monday_client_id", "")
    client_secret = getattr(settings, "monday_client_secret", "")
    redirect_uri = getattr(settings, "monday_redirect_uri", "")

    if not client_id or not client_secret:
        return HTMLResponse(_popup_html(False, "monday", "no_credentials"), 500)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(MONDAY_TOKEN_URL, json={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            })
            resp.raise_for_status()
            tokens = resp.json()
    except Exception as exc:
        logger.error("Monday token exchange failed: %s", exc)
        return HTMLResponse(_popup_html(False, "monday", "token_exchange_failed"), 502)

    access_token = tokens.get("access_token")
    if not access_token:
        return HTMLResponse(_popup_html(False, "monday", "no_token"), 502)

    # Fetch account name via Monday API
    account_name = ""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            me_resp = await client.post(
                "https://api.monday.com/v2",
                headers={"Authorization": access_token},
                json={"query": "{ me { name email account { name } } }"},
            )
            if me_resp.status_code == 200:
                me_data = me_resp.json().get("data", {}).get("me", {})
                account_name = me_data.get("email", "") or me_data.get("name", "")
    except Exception:
        pass

    store = ConfigStore()
    cfg = store.load()
    cfg["monday_token"] = access_token
    cfg["monday_account_name"] = account_name
    store.save(cfg)
    reset_settings()

    logger.info("Monday OAuth token acquired for %s", account_name or "unknown")
    return HTMLResponse(_popup_html(True, "monday"))
