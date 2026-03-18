"""
AutoHelper entrypoint - runs uvicorn server or Windows service.

Modes:
    (no flag)           → console mode
    --service install   → register Windows service
    --service remove    → deregister Windows service
    --service start     → start via SCM
    --service stop      → stop via SCM
"""

import atexit
import os
import sys
from pathlib import Path

import uvicorn

from autohelper.app import build_app
from autohelper.config import get_settings
from autohelper.shared.paths import data_dir
from autohelper.shared.platform import is_windows, platform_label

# Expose app for uvicorn factory/import
app = build_app()

LOCKFILE = data_dir() / "autohelper.pid"


def _acquire_lock() -> bool:
    """
    Acquire PID lockfile to prevent simultaneous service + tray instances.

    Returns True if lock acquired, False if another instance is running.
    """
    if LOCKFILE.exists():
        try:
            stored_pid = int(LOCKFILE.read_text().strip())
            # Check if the process is still alive
            if is_windows():
                import ctypes
                kernel32 = ctypes.windll.kernel32
                handle = kernel32.OpenProcess(0x0400, False, stored_pid)  # PROCESS_QUERY_INFORMATION
                if handle:
                    kernel32.CloseHandle(handle)
                    return False  # Process still running
            else:
                os.kill(stored_pid, 0)
                return False  # Process still running
        except (ValueError, OSError, AttributeError):
            # Stale lockfile or process gone
            pass

    LOCKFILE.parent.mkdir(parents=True, exist_ok=True)
    LOCKFILE.write_text(str(os.getpid()))
    atexit.register(_release_lock)
    return True


def _release_lock() -> None:
    """Release PID lockfile."""
    try:
        if LOCKFILE.exists():
            stored_pid = int(LOCKFILE.read_text().strip())
            if stored_pid == os.getpid():
                LOCKFILE.unlink(missing_ok=True)
    except Exception:
        pass


def _kill_existing() -> None:
    """Kill any running AutoHelper instance and clean up the lock file."""
    if not LOCKFILE.exists():
        return
    try:
        stored_pid = int(LOCKFILE.read_text().strip())
    except (ValueError, OSError):
        LOCKFILE.unlink(missing_ok=True)
        return

    # Try to kill the process
    try:
        if is_windows():
            import signal
            os.kill(stored_pid, signal.SIGTERM)
        else:
            os.kill(stored_pid, 15)  # SIGTERM
        print(f"Killed existing AutoHelper (PID {stored_pid})")
        # Give it a moment to release the port
        import time
        time.sleep(0.5)
    except OSError:
        pass  # Process already gone

    LOCKFILE.unlink(missing_ok=True)


def _check_port_conflict(host: str, port: int) -> None:
    """Check if port is already in use. Exit cleanly if healthy instance exists."""
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        if result != 0:
            return  # Port is free
    finally:
        sock.close()

    # Port is in use — check if it's a healthy AutoHelper instance
    import urllib.request

    try:
        req = urllib.request.Request(f"http://{host}:{port}/health")
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                print(f"AutoHelper already running on {host}:{port}, exiting.")
                sys.exit(0)
    except Exception:
        pass

    # Port in use but not a healthy AutoHelper
    print(
        f"Port {port} is in use but not responding to health check. Exiting.",
        file=sys.stderr,
    )
    sys.exit(1)


def _handle_service(action: str) -> None:
    """Handle --service subcommands."""
    from autohelper.winservice import (
        install_service,
        remove_service,
        run_service_dispatcher,
        start_service,
        stop_service,
    )

    actions = {
        "install": install_service,
        "remove": remove_service,
        "start": start_service,
        "stop": stop_service,
    }

    if action in actions:
        actions[action]()
    else:
        print(f"Unknown service action: {action}")
        print("Valid actions: install, remove, start, stop")
        sys.exit(1)


def main() -> None:
    """Run the AutoHelper server."""
    args = sys.argv[1:]

    # Handle --service subcommands
    if "--service" in args:
        idx = args.index("--service")
        action = args[idx + 1] if idx + 1 < len(args) else ""
        _handle_service(action)
        return

    # In dev mode, kill any existing instance first
    if "--dev" in args:
        args.remove("--dev")
        _kill_existing()

    # Acquire PID lock before any server mode
    if not _acquire_lock():
        print("ERROR: Another AutoHelper instance is already running.")
        print(f"Lock file: {LOCKFILE}")
        sys.exit(1)

    # Check if started by Windows SCM (no args, frozen exe)
    if getattr(sys, "frozen", False) and not args:
        # PyInstaller exe with no args — could be SCM invocation
        try:
            from autohelper.winservice import run_service_dispatcher
            run_service_dispatcher()
            return
        except Exception:
            pass  # Fall through to console mode

    settings = get_settings()

    # Check for port conflict before starting
    _check_port_conflict(settings.host, settings.port)

    print(f"Starting AutoHelper on http://{settings.host}:{settings.port}")
    print(f"Dashboard: http://{settings.host}:{settings.port}/dashboard")
    print(f"Docs: http://{settings.host}:{settings.port}/docs")
    print(f"Platform: {platform_label()}")

    config = uvicorn.Config(
        build_app(settings),
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        loop="asyncio",
    )
    server = uvicorn.Server(config)

    server.run()


if __name__ == "__main__":
    main()
