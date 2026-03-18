"""Config module routes - read/write persistent config (data/config.json)."""

import threading
from typing import Any

from fastapi import APIRouter

from autohelper.config import reset_settings
from autohelper.config.manifest import schema_as_dict
from autohelper.config.store import ConfigStore
from autohelper.shared.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/config", tags=["config"])


def _open_folder_dialog() -> str | None:
    """Open native folder picker dialog. Must run on main thread for some platforms."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        # Create and hide root window
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)  # Bring dialog to front

        # Open folder picker
        folder = filedialog.askdirectory(
            title="Select folder",
            mustexist=True,
        )

        root.destroy()
        return folder if folder else None
    except Exception as e:
        logger.warning("Failed to open folder dialog: %s", e)
        return None


@router.post("/select-folder")
async def select_folder() -> dict[str, Any]:
    """
    Open a native folder picker dialog and return the selected path.
    Returns {"path": "/selected/path"} or {"path": null} if cancelled.
    """
    # tkinter needs to run on main thread on macOS, use threading event to wait
    result: dict[str, str | None] = {"path": None}
    done = threading.Event()

    def run_dialog() -> None:
        result["path"] = _open_folder_dialog()
        done.set()

    # Run in thread and wait (FastAPI runs in thread pool anyway)
    thread = threading.Thread(target=run_dialog)
    thread.start()
    done.wait(timeout=120)  # 2 minute timeout for user to select

    return {"path": result["path"]}


@router.get("/schema")
async def get_schema() -> dict[str, Any]:
    """Return the settings manifest as JSON for dynamic UI rendering."""
    return schema_as_dict()


@router.get("")
async def get_config() -> dict[str, Any]:
    """Return the current persistent config."""
    store = ConfigStore()
    return store.load()


@router.put("")
async def put_config(body: dict[str, Any]) -> dict[str, Any]:
    """
    Merge body into existing config, save, and reinitialise dependents.

    Returns the merged config.
    """
    store = ConfigStore()
    current = store.load()
    current.update(body)
    store.save(current)

    # Reset cached Settings so next access picks up new values
    reset_settings()

    # Reinitialise mail service with potentially updated settings
    try:
        from autohelper.modules.mail import MailService

        svc = MailService()
        svc.stop()
        # Re-read settings and apply persisted config values
        from autohelper.config import get_settings

        settings = get_settings()
        if "mail_enabled" in current:
            settings.mail_enabled = bool(current["mail_enabled"])
        if "mail_poll_interval" in current:
            settings.mail_poll_interval = int(current["mail_poll_interval"])

        svc.settings = settings
        svc.start()
    except Exception as exc:
        logger.warning("Failed to reinit mail service after config change: %s", exc)

    # Reinitialise context service so link key and other
    # context-layer settings take effect without a restart.
    try:
        from autohelper.modules.context.service import ContextService

        ctx = ContextService()
        ctx.reinit_clients()
    except Exception as exc:
        logger.warning("Failed to reinit context service after config change: %s", exc)

    return current
