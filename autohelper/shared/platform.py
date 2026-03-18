"""
Platform detection utilities.

Distinguishes between native Windows, WSL2 (Linux under Windows),
native Linux, and macOS to gate platform-specific features like
Outlook COM automation and system tray icons.
"""

import functools
import os
import sys


@functools.cache
def is_windows() -> bool:
    """True on native Windows (not WSL)."""
    return sys.platform == "win32"


@functools.cache
def is_wsl() -> bool:
    """True when running inside Windows Subsystem for Linux."""
    if sys.platform != "linux":
        return False
    try:
        with open("/proc/version", "r") as f:
            return "microsoft" in f.read().lower()
    except OSError:
        return False


@functools.cache
def is_linux() -> bool:
    """True on native Linux (not WSL)."""
    return sys.platform == "linux" and not is_wsl()


@functools.cache
def is_macos() -> bool:
    return sys.platform == "darwin"


@functools.cache
def has_display_server() -> bool:
    """True when a display server (X11/Wayland) is available for GUI."""
    if is_windows():
        return True
    # Check for X11 or Wayland display
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


@functools.cache
def has_dbus_tray() -> bool:
    """True when D-Bus StatusNotifier (system tray) support is likely available."""
    if is_windows():
        return True  # Windows uses native tray, not D-Bus
    if is_wsl():
        return False  # WSL2 lacks a desktop environment
    # On native Linux, check for a running D-Bus session
    return bool(os.environ.get("DBUS_SESSION_BUS_ADDRESS"))


@functools.cache
def platform_label() -> str:
    """Human-readable platform label for log messages."""
    if is_windows():
        return "Windows"
    if is_wsl():
        return "WSL2 (Linux)"
    if is_macos():
        return "macOS"
    return "Linux"


@functools.cache
def can_use_outlook() -> bool:
    """True only on native Windows where COM/Outlook automation is possible."""
    return is_windows()
