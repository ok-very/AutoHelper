"""Integration status endpoint — returns source-attributed connection state."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from autohelper.config import get_settings
from autohelper.config.store import ConfigStore
from autohelper.shared.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])


def _source_of(key: str, settings: Any, raw_cfg: dict[str, Any]) -> str:
    """Determine where a setting value came from: 'env', 'config', or 'none'."""
    effective = getattr(settings, key, "")
    if effective in (None, "", []):
        return "none"
    in_config = raw_cfg.get(key, "")
    if in_config not in (None, "", []):
        return "config"
    return "env"


def _field_status(key: str, settings: Any, raw_cfg: dict[str, Any]) -> dict[str, Any]:
    """Return {value, source} for a non-secret field."""
    return {
        "value": getattr(settings, key, "") or "",
        "source": _source_of(key, settings, raw_cfg),
    }


def _token_hint(value: str) -> str | None:
    """Return a masked preview of a token (first 5 + last 3 chars)."""
    if not value or len(value) < 10:
        return None
    return f"{value[:5]}...{value[-3:]}"


def _get_autoart_connections(settings: Any, raw_cfg: dict[str, Any]) -> dict[str, Any]:
    """Check autoart pairing status and proxy OAuth connection statuses."""
    paired = bool(getattr(settings, "autoart_link_key", ""))
    result: dict[str, Any] = {"paired": paired}

    if not paired:
        return result

    try:
        from autohelper.modules.context.autoart import AutoArtClient

        api_url = getattr(settings, "autoart_api_url", "http://localhost:3001")
        link_key = raw_cfg.get("autoart_link_key") or getattr(
            settings, "autoart_link_key", ""
        )
        client = AutoArtClient(api_url=api_url, link_key=link_key or None)
        connections = client.get_linked_connection_status()
        if connections:
            result["connections"] = connections
    except Exception as exc:
        logger.debug("Could not fetch autoart connection status: %s", exc)

    return result


@router.get("/status")
async def integrations_status() -> dict[str, Any]:
    """Return source-attributed status for all integrations."""
    settings = get_settings()
    raw_cfg = ConfigStore().load()

    token_val = getattr(settings, "clickup_token", "") or ""

    return {
        "clickup": {
            "configured": bool(token_val),
            "source": _source_of("clickup_token", settings, raw_cfg),
            "token_hint": _token_hint(token_val),
            "oauth_available": bool(getattr(settings, "clickup_client_id", "")),
            "redirect_uri": getattr(settings, "clickup_redirect_uri", "") or "",
            "workspace_id": _field_status("clickup_workspace_id", settings, raw_cfg),
            "space_id": _field_status("clickup_space_id", settings, raw_cfg),
            "list_id": _field_status("clickup_list_id", settings, raw_cfg),
        },
        "google": {
            "oauth_available": bool(getattr(settings, "google_client_id", "")),
            "configured": bool(raw_cfg.get("google_token", "")),
            "account": raw_cfg.get("google_account_name", ""),
            "redirect_uri": getattr(settings, "google_redirect_uri", "") or "",
            "has_refresh_token": bool(raw_cfg.get("google_refresh_token", "")),
        },
        "monday": {
            "oauth_available": bool(getattr(settings, "monday_client_id", "")),
            "configured": bool(raw_cfg.get("monday_token", "")),
            "account": raw_cfg.get("monday_account_name", ""),
            "redirect_uri": getattr(settings, "monday_redirect_uri", "") or "",
        },
        "exchange": {
            "configured": bool(getattr(settings, "exchange_email", "")),
            "source": _source_of("exchange_email", settings, raw_cfg),
            "email": _field_status("exchange_email", settings, raw_cfg),
        },
        "autoart": _get_autoart_connections(settings, raw_cfg),
    }
