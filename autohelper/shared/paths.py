"""
Platform-aware data directory for AutoHelper.

Returns a stable, deployment-safe path for persistent data (DB, config)
regardless of working directory:

    Windows:  %LOCALAPPDATA%/AutoHelper
    Linux:    ~/.local/share/autohelper
    macOS:    ~/Library/Application Support/AutoHelper

Override with AUTOHELPER_DATA_DIR env var (e.g. AUTOHELPER_DATA_DIR=./data for dev).
"""

import functools
import os
import sys
from pathlib import Path


@functools.cache
def data_dir() -> Path:
    """Return (and create) the platform data directory for AutoHelper."""
    override = os.environ.get("AUTOHELPER_DATA_DIR")
    if override:
        p = Path(override).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        p = base / "AutoHelper"
    elif sys.platform == "darwin":
        p = Path.home() / "Library" / "Application Support" / "AutoHelper"
    else:
        # Linux / WSL — XDG_DATA_HOME or ~/.local/share
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        p = base / "autohelper"

    p.mkdir(parents=True, exist_ok=True)
    return p
