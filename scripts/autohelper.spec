# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for AutoHelper.

Produces one executable:
- autohelper.exe (console) - for service registration, CLI, and Electron child process
"""

import os
import sys
from pathlib import Path

block_cipher = None

# Paths
ROOT = Path(SPECPATH).parent
PACKAGE = ROOT / "autohelper"
MIGRATIONS = PACKAGE / "db" / "migrations"
POWERSHELL = PACKAGE / "modules" / "contacts" / "powershell"
DASHBOARD = PACKAGE / "gui" / "dashboard"
ARTISTS_GUI = PACKAGE / "gui" / "artists"
ARTISTS_DIST = PACKAGE / "gui" / "artists-dist"

# Data files to bundle
datas = [
    (str(MIGRATIONS), "autohelper/db/migrations"),
    (str(POWERSHELL), "autohelper/modules/contacts/powershell"),
    (str(DASHBOARD), "autohelper/gui/dashboard"),
    (str(ARTISTS_GUI), "autohelper/gui/artists"),
]

# Include Vite-built artists-dist if it exists
if ARTISTS_DIST.is_dir():
    datas.append((str(ARTISTS_DIST), "autohelper/gui/artists-dist"))

# Hidden imports that PyInstaller misses (dynamic imports, plugins, etc.)
hiddenimports = [
    # Uvicorn internals
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.wsproto_impl",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    # Pydantic
    "pydantic",
    "pydantic_settings",
    "pydantic.deprecated.decorator",
    # APScheduler
    "apscheduler.schedulers.asyncio",
    "apscheduler.triggers.interval",
    "apscheduler.triggers.cron",
    "apscheduler.triggers.date",
    "apscheduler.executors.pool",
    "apscheduler.jobstores.memory",
    # FastAPI / Starlette
    "fastapi",
    "starlette.staticfiles",
    "starlette.responses",
    "starlette.middleware.cors",
    "multipart",
    # Win32
    "win32serviceutil",
    "win32service",
    "win32event",
    "servicemanager",
    "win32api",
    "win32timezone",
    # Database
    "sqlite3",
    # Other
    "zoneinfo",
    "httpx",
    "PIL",
    "email.mime.text",
    "email.mime.multipart",
]

# Common analysis
a = Analysis(
    [str(PACKAGE / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "unittest", "test", "pytest",
        # GUI / heavy packages no longer needed (Electron owns the tray)
        "pystray",
        "tkinter", "_tkinter", "tk", "tcl",
        "matplotlib", "numpy", "scipy", "pandas",
        "IPython", "notebook", "jupyter",
        "docutils", "sphinx",
        "setuptools", "distutils", "pkg_resources",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Console executable (for service and CLI)
console_exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="autohelper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    icon=None,
)

coll = COLLECT(
    console_exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="autohelper",
)
