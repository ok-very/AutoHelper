"""Pairing router — claim, status, and unpair endpoints.

POST /pair/claim   Programmatic pairing (dev scripts, headless environments).
GET  /pair/status  Check current pairing state.
POST /pair/unpair  Clear the local link key so the tray updates immediately.
"""

import json
import threading
import urllib.error
import urllib.request
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from autohelper.config import get_settings, reset_settings
from autohelper.config.store import ConfigStore
from autohelper.shared.logging import get_logger
from autohelper.sync.connection_state import ConnectionState, ConnectionStateManager
from autohelper.sync.poller import start_backend_poller

logger = get_logger(__name__)

router = APIRouter(prefix="/pair", tags=["pairing"])


# -- Request/Response models --------------------------------------------------


class ClaimRequest(BaseModel):
    code: str
    backend_url: str


class ClaimResponse(BaseModel):
    paired: bool
    error: Optional[str] = None


class StatusResponse(BaseModel):
    paired: bool
    backend_url: Optional[str] = None


class UnpairResponse(BaseModel):
    paired: bool


@router.post("/claim", response_model=ClaimResponse)
def claim(body: ClaimRequest) -> ClaimResponse:
    """Redeem a pairing code against the backend and store the link key."""
    redeem_url = f"{body.backend_url.rstrip('/')}/api/pair/redeem"
    payload = json.dumps({"code": body.code}).encode()
    req = urllib.request.Request(
        redeem_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        logger.warning("Backend redeem returned %s for code %.4s…", exc.code, body.code)
        return ClaimResponse(paired=False, error="Invalid or expired code")
    except Exception as exc:
        logger.error("Failed to reach backend at %s: %s", redeem_url, exc)
        return ClaimResponse(paired=False, error=f"Cannot reach backend: {exc}")

    key = data.get("key", "")
    if not key:
        return ClaimResponse(paired=False, error="Backend returned empty key")

    store = ConfigStore()
    cfg = store.load()
    cfg["autoart_link_key"] = key
    cfg["autoart_api_url"] = body.backend_url
    store.save(cfg)

    reset_settings()
    start_backend_poller()

    # Update connection state
    ConnectionStateManager().set_state(ConnectionState.PAIRED_CONNECTED)

    logger.info("Paired via /pair/claim (backend %s)", body.backend_url)
    return ClaimResponse(paired=True)


@router.get("/status", response_model=StatusResponse)
def status() -> StatusResponse:
    """Return current pairing state."""
    settings = get_settings()
    paired = bool(settings.autoart_link_key)
    return StatusResponse(
        paired=paired,
        backend_url=settings.autoart_api_url if paired else None,
    )


def _reinit_clients_background() -> None:
    """Reinit context clients in background thread."""
    try:
        from autohelper.modules.context.service import ContextService

        ContextService().reinit_clients()
    except Exception as exc:
        logger.warning("Failed to reinit context service after unpair: %s", exc)


@router.post("/unpair", response_model=UnpairResponse)
def unpair() -> UnpairResponse:
    """Clear the local link key."""
    store = ConfigStore()
    cfg = store.load()

    cfg.pop("autoart_link_key", None)
    # Clean up legacy keys too
    cfg.pop("autoart_session_id", None)
    cfg.pop("autoart_api_key", None)
    store.save(cfg)

    reset_settings()

    # Update connection state
    ConnectionStateManager().set_state(ConnectionState.UNPAIRED)

    # Reinit in background to avoid blocking the HTTP response
    threading.Thread(target=_reinit_clients_background, daemon=True).start()

    logger.info("Unpaired via HTTP endpoint")
    return UnpairResponse(paired=False)
