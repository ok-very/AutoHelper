"""Windows Service wrapper for AutoHelper using pywin32.

Registers AutoHelper as a Windows service that runs the FastAPI server
and all background schedulers.

Usage:
    autohelper.exe --service install   # Register service
    autohelper.exe --service remove    # Deregister service
    autohelper.exe --service start     # Start via SCM
    autohelper.exe --service stop      # Stop via SCM
"""

import logging
import sys
import threading

logger = logging.getLogger(__name__)

# Only import win32 modules on Windows
try:
    import servicemanager
    import win32event
    import win32service
    import win32serviceutil

    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


if HAS_WIN32:

    class AutoHelperService(win32serviceutil.ServiceFramework):
        """Windows Service implementation for AutoHelper."""

        _svc_name_ = "AutoHelper"
        _svc_display_name_ = "AutoHelper Service"
        _svc_description_ = (
            "Local filesystem orchestration and contact sync service. "
            "Provides file indexing, mail polling, contact synchronization, "
            "and integration with AutoArt."
        )

        def __init__(self, args: list) -> None:
            win32serviceutil.ServiceFramework.__init__(self, args)
            self._stop_event = win32event.CreateEvent(None, 0, 0, None)
            self._server = None
            self._server_thread = None

        def SvcStop(self) -> None:
            """Handle service stop request from SCM."""
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            logger.info("AutoHelper service stop requested")

            if self._server:
                self._server.should_exit = True

            win32event.SetEvent(self._stop_event)

        def SvcDoRun(self) -> None:
            """Main service entry point - runs the FastAPI server."""
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, ""),
            )

            try:
                self._run_server()
            except Exception as e:
                servicemanager.LogErrorMsg(f"AutoHelper service failed: {e}")
                logger.exception("Service failed")

            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STOPPED,
                (self._svc_name_, ""),
            )

        def _run_server(self) -> None:
            """Start uvicorn in a background thread and wait for stop signal."""
            import uvicorn

            from autohelper.app import build_app
            from autohelper.config import get_settings

            settings = get_settings()

            config = uvicorn.Config(
                build_app(settings),
                host=settings.host,
                port=settings.port,
                log_level=settings.log_level.lower(),
                loop="asyncio",
            )
            self._server = uvicorn.Server(config)

            self._server_thread = threading.Thread(
                target=self._server.run, daemon=True
            )
            self._server_thread.start()

            logger.info(
                "AutoHelper service started on http://%s:%s",
                settings.host,
                settings.port,
            )

            # Wait for stop event
            win32event.WaitForSingleObject(self._stop_event, win32event.INFINITE)

            # Graceful shutdown
            if self._server:
                self._server.should_exit = True

            if self._server_thread:
                self._server_thread.join(timeout=10)

            logger.info("AutoHelper service stopped")


def install_service() -> None:
    """Register the Windows service."""
    if not HAS_WIN32:
        print("ERROR: pywin32 is required for Windows service support.")
        print("Install it with: pip install pywin32")
        sys.exit(1)

    # Use the current executable as the service binary
    exe_path = sys.executable
    if exe_path.endswith("python.exe") or exe_path.endswith("python3.exe"):
        # Running from Python interpreter - use module invocation
        win32serviceutil.InstallService(
            AutoHelperService,
            AutoHelperService._svc_name_,
            AutoHelperService._svc_display_name_,
            startType=win32service.SERVICE_AUTO_START,
            description=AutoHelperService._svc_description_,
        )
    else:
        # Running from PyInstaller exe
        win32serviceutil.HandleCommandLine(AutoHelperService, argv=["", "install"])

    print(f"Service '{AutoHelperService._svc_name_}' installed successfully.")
    print(f"Start with: net start {AutoHelperService._svc_name_}")


def remove_service() -> None:
    """Deregister the Windows service."""
    if not HAS_WIN32:
        print("ERROR: pywin32 is required for Windows service support.")
        sys.exit(1)

    win32serviceutil.HandleCommandLine(AutoHelperService, argv=["", "remove"])
    print(f"Service '{AutoHelperService._svc_name_}' removed.")


def start_service() -> None:
    """Start the service via SCM."""
    if not HAS_WIN32:
        print("ERROR: pywin32 is required for Windows service support.")
        sys.exit(1)

    win32serviceutil.HandleCommandLine(AutoHelperService, argv=["", "start"])


def stop_service() -> None:
    """Stop the service via SCM."""
    if not HAS_WIN32:
        print("ERROR: pywin32 is required for Windows service support.")
        sys.exit(1)

    win32serviceutil.HandleCommandLine(AutoHelperService, argv=["", "stop"])


def run_service_dispatcher() -> None:
    """Called when started by the Windows SCM (not by user)."""
    if not HAS_WIN32:
        print("ERROR: pywin32 is required for Windows service support.")
        sys.exit(1)

    servicemanager.Initialize()
    servicemanager.PrepareToHostSingle(AutoHelperService)
    servicemanager.StartServiceCtrlDispatcher()
