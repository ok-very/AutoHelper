"""
Backend Poller - Syncs settings and executes commands from AutoArt backend.

Polls the backend every 5 seconds for:
- Settings changes (applies to local config if version changed)
- Pending commands (executes and acknowledges)

Also sends heartbeat with current status.
"""

import asyncio
import json
import threading
import urllib.error
import urllib.request
from typing import Any, cast

from autohelper.config import get_settings, reset_settings
from autohelper.config.manifest import CONFIG_KEYS
from autohelper.config.store import ConfigStore
from autohelper.shared.logging import get_logger
from autohelper.sync.connection_state import ConnectionState, ConnectionStateManager

logger = get_logger(__name__)

# Global poller instance
_poller: "BackendPoller | None" = None


class BackendPoller:
    """
    Background thread that polls the AutoArt backend for settings and commands.
    """

    def __init__(self, poll_interval: float = 5.0) -> None:
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_settings_version: int = 0
        self._running_commands: set[str] = set()

    def start(self) -> None:
        """Start the polling thread."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("Backend poller already running")
            return

        # Set initial state - optimistic if we have a link key
        settings = get_settings()
        state_mgr = ConnectionStateManager()
        if settings.autoart_link_key:
            state_mgr.set_state(ConnectionState.PAIRED_CONNECTED)
        else:
            state_mgr.set_state(ConnectionState.UNPAIRED)

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("Backend poller started (interval: %ss)", self.poll_interval)

    def stop(self) -> None:
        """Stop the polling thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=10)
            self._thread = None
        logger.info("Backend poller stopped")

    def _poll_loop(self) -> None:
        """Main polling loop."""
        while not self._stop_event.wait(self.poll_interval):
            try:
                self._poll_once()
            except Exception:
                logger.exception("Backend poll failed")

    def _poll_once(self) -> None:
        """Single poll iteration: heartbeat + fetch settings/commands."""
        settings = get_settings()
        state_mgr = ConnectionStateManager()

        # Skip if not paired
        if not settings.autoart_link_key:
            state_mgr.set_state(ConnectionState.UNPAIRED)
            return

        base_url = settings.autoart_api_url

        # 1. Send heartbeat with current status
        try:
            status = self._gather_status()
            self._post(f"{base_url}/api/autohelper/heartbeat", {"status": status})
        except urllib.error.HTTPError as e:
            if e.code == 401:
                logger.warning("Link key invalid or expired, clearing pairing")
                self._clear_pairing()
                state_mgr.set_state(ConnectionState.UNPAIRED)
                return
            else:
                logger.debug("Heartbeat failed: HTTP %d", e.code)
                state_mgr.set_state(ConnectionState.PAIRED_DISCONNECTED)
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            logger.debug("Heartbeat failed: network error: %s", e)
            state_mgr.set_state(ConnectionState.PAIRED_DISCONNECTED)
        except Exception as e:
            logger.debug("Heartbeat failed: %s", e)
            state_mgr.set_state(ConnectionState.PAIRED_DISCONNECTED)

        # 2. Poll for settings and commands
        try:
            poll_response = self._get(f"{base_url}/api/autohelper/poll")
            # Successful poll - we're connected
            state_mgr.set_state(ConnectionState.PAIRED_CONNECTED)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                logger.warning("Link key invalid or expired, clearing pairing")
                self._clear_pairing()
                state_mgr.set_state(ConnectionState.UNPAIRED)
            else:
                logger.debug("Poll failed: HTTP %d", e.code)
                state_mgr.set_state(ConnectionState.PAIRED_DISCONNECTED)
            return
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            logger.debug("Poll failed: network error: %s", e)
            state_mgr.set_state(ConnectionState.PAIRED_DISCONNECTED)
            return
        except Exception as e:
            logger.debug("Poll failed: %s", e)
            state_mgr.set_state(ConnectionState.PAIRED_DISCONNECTED)
            return

        # 3. Apply settings if version changed
        new_version = poll_response.get("settingsVersion", 0)
        if new_version > self._last_settings_version:
            self._apply_settings(poll_response.get("settings", {}))
            self._last_settings_version = new_version

        # 4. Execute pending commands
        commands = poll_response.get("commands", [])
        for cmd in commands:
            cmd_id = cmd.get("id")
            if cmd_id and cmd_id not in self._running_commands:
                self._execute_command(cmd_id, cmd.get("type"), cmd.get("payload", {}))

    def _gather_status(self) -> dict[str, Any]:
        """Gather current AutoHelper status for heartbeat."""
        status: dict[str, Any] = {}

        # Database status
        try:
            from autohelper.db import get_db
            from autohelper.db.migrate import get_migration_status

            db = get_db()
            settings = get_settings()
            db.execute("SELECT 1")
            mig = get_migration_status(db)
            status["database"] = {
                "connected": True,
                "path": str(settings.db_path),
                "migration_status": (
                    "current"
                    if mig["pending_count"] == 0
                    else f"{mig['pending_count']} pending"
                ),
            }
        except Exception:
            status["database"] = {"connected": False, "path": "", "migration_status": "unknown"}

        # Runner status
        try:
            from autohelper.modules.runner import get_runner_service

            runner_svc = get_runner_service()
            runner_status = runner_svc.get_status()
            status["runner"] = {
                "active": runner_status.active,
                "current_runner": runner_status.current_runner.value if runner_status.current_runner else None,
            }
        except Exception:
            status["runner"] = {"active": False}

        # Index status
        try:
            from autohelper.modules.index.service import IndexService

            index_svc = IndexService()
            index_status = index_svc.get_status()
            last_run = index_status.get("last_run")
            status["index"] = {
                "status": "running" if index_status.get("is_running") else "idle",
                "total_files": index_status.get("total_files", 0),
                "last_run": last_run.isoformat() if last_run is not None else None,
            }
        except Exception:
            status["index"] = {"status": "unknown"}

        # Mail status
        try:
            from autohelper.modules.mail import MailService

            mail_svc = MailService()
            status["mail"] = {
                "enabled": get_settings().mail_enabled,
                "running": mail_svc.running,
            }
        except Exception:
            status["mail"] = {"enabled": False, "running": False}

        # GC status
        try:
            from autohelper.modules.gc.scheduler import get_scheduler
            from autohelper.modules.gc.service import GarbageCollectionService

            gc_svc = GarbageCollectionService()
            scheduler = get_scheduler()
            last_run = None
            if gc_svc.last_result and gc_svc.last_result.completed_at:
                last_run = gc_svc.last_result.completed_at.isoformat()
            status["gc"] = {
                "enabled": get_settings().gc_enabled,
                "last_run": last_run,
            }
        except Exception:
            status["gc"] = {"enabled": False}

        # Adapter availability
        status["adapters"] = self._gather_adapters()

        return status

    def _gather_adapters(self) -> list[dict[str, Any]]:
        """Gather available adapter information."""
        adapters: list[dict[str, Any]] = []

        # PDF - AutoHelper only (uses pdfplumber)
        try:
            import pdfplumber
            adapters.append({"name": "PDF", "available": True, "handler": "autohelper"})
        except ImportError:
            adapters.append({"name": "PDF", "available": False, "handler": "autohelper"})

        # DOCX - backend fallback available
        try:
            import docx
            adapters.append({"name": "DOCX", "available": True, "handler": "autohelper"})
        except ImportError:
            adapters.append({"name": "DOCX", "available": True, "handler": "backend"})

        # CSV - backend handles this
        adapters.append({"name": "CSV", "available": True, "handler": "backend"})

        # XLSX - backend handles this
        adapters.append({"name": "XLSX", "available": True, "handler": "backend"})

        # Web Collector - check actual dependencies directly
        web_collector_available = True
        web_collector_missing: list[str] = []

        try:
            import httpx  # noqa: F401
        except ImportError:
            web_collector_available = False
            web_collector_missing.append("httpx")

        try:
            from bs4 import BeautifulSoup  # noqa: F401
        except ImportError:
            web_collector_available = False
            web_collector_missing.append("beautifulsoup4")

        # lxml is optional, falls back to html.parser
        if web_collector_missing:
            logger.warning("Web Collector unavailable, missing: %s", web_collector_missing)

        adapters.append({
            "name": "Web Collector",
            "available": web_collector_available,
            "handler": "autohelper",
        })

        # Mail Poller - AutoHelper with backend MS Graph fallback
        try:
            from autohelper.modules.mail import MailService

            mail_svc = MailService()
            # If mail is running, report as autohelper; otherwise backend may have MS Graph
            adapters.append({
                "name": "Mail Poller",
                "available": True,
                "handler": "autohelper" if mail_svc.running else "backend",
            })
        except Exception:
            adapters.append({"name": "Mail Poller", "available": True, "handler": "backend"})

        return adapters

    def _apply_settings(self, new_settings: dict[str, Any]) -> None:
        """Apply settings from backend to local config."""
        logger.info("Applying settings from backend (version %d)", self._last_settings_version + 1)

        # Map backend settings to local config keys
        store = ConfigStore()
        cfg = store.load()

        # Apply any key the manifest knows about
        for key in CONFIG_KEYS:
            if key in new_settings:
                cfg[key] = new_settings[key]

        store.save(cfg)
        reset_settings()

        # Restart mail service if enabled state changed
        try:
            from autohelper.modules.mail import MailService

            mail_svc = MailService()
            new_mail_enabled = new_settings.get("mail_enabled", False)
            if new_mail_enabled and not mail_svc.running:
                mail_svc.start()
            elif not new_mail_enabled and mail_svc.running:
                mail_svc.stop()
        except Exception as e:
            logger.warning("Failed to update mail service: %s", e)

        logger.info("Settings applied successfully")

    def _execute_command(
        self, cmd_id: str, cmd_type: str | None, payload: dict[str, Any]
    ) -> None:
        """Execute a command from the backend."""
        if not cmd_type:
            return

        self._running_commands.add(cmd_id)
        logger.info("Executing command %s: %s", cmd_id, cmd_type)

        # Mark as running
        try:
            settings = get_settings()
            self._post(f"{settings.autoart_api_url}/api/autohelper/commands/{cmd_id}/start", {})
        except Exception as e:
            logger.warning("Failed to mark command as running: %s", e)

        # Execute in background thread
        def run_command() -> None:
            success = False
            result: dict[str, Any] | None = None

            try:
                if cmd_type == "rescan_index":
                    result = self._cmd_rescan_index()
                    success = True
                elif cmd_type == "rebuild_index":
                    result = self._cmd_rebuild_index()
                    success = True
                elif cmd_type == "run_collector":
                    result = self._cmd_run_collector(payload)
                    success = result.get("success", False) if result else False
                elif cmd_type == "start_mail":
                    result = self._cmd_start_mail()
                    success = True
                elif cmd_type == "stop_mail":
                    result = self._cmd_stop_mail()
                    success = True
                elif cmd_type == "run_gc":
                    result = self._cmd_run_gc()
                    success = True
                elif cmd_type == "select_folder":
                    result = self._cmd_select_folder()
                    success = True
                elif cmd_type == "ping":
                    result = self._cmd_ping()
                    success = True
                elif cmd_type == "watch_root":
                    result = self._cmd_watch_root(payload)
                    success = result.get("success", False) if result else False
                elif cmd_type == "unwatch_root":
                    result = self._cmd_unwatch_root(payload)
                    success = result.get("success", False) if result else False
                elif cmd_type == "drain_file_events":
                    result = self._cmd_drain_file_events()
                    success = True
                elif cmd_type == "execute_manifest":
                    result = self._cmd_execute_manifest(payload)
                    success = result.get("failed", 0) == 0 if result else False
                else:
                    logger.warning("Unknown command type: %s", cmd_type)
                    result = {"error": f"Unknown command: {cmd_type}"}
            except Exception as e:
                logger.exception("Command %s failed", cmd_type)
                result = {"error": str(e)}

            # Acknowledge completion
            try:
                settings = get_settings()
                self._post(
                    f"{settings.autoart_api_url}/api/autohelper/commands/{cmd_id}/ack",
                    {"success": success, "result": result},
                )
            except Exception as e:
                logger.warning("Failed to acknowledge command: %s", e)
            finally:
                self._running_commands.discard(cmd_id)

        threading.Thread(target=run_command, daemon=True).start()

    def _cmd_rescan_index(self) -> dict[str, Any]:
        """Execute rescan_index command."""
        from autohelper.modules.index.service import IndexService

        svc = IndexService()
        result = svc.rescan()
        return {"run_id": result.run_id, "status": result.status, "started_at": result.started_at.isoformat()}

    def _cmd_rebuild_index(self) -> dict[str, Any]:
        """Execute rebuild_index command."""
        from autohelper.modules.index.service import IndexService

        svc = IndexService()
        result = svc.rebuild_index()
        return {"run_id": result.run_id, "status": result.status, "started_at": result.started_at.isoformat()}

    def _cmd_run_collector(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute run_collector command."""
        url = payload.get("url")
        if not url:
            return {"success": False, "error": "No URL provided"}

        # Run collector synchronously (it's already in a background thread)
        from pathlib import Path

        from autohelper.modules.runner import get_runner_service
        from autohelper.modules.runner.types import InvokeRequest, RunnerId

        runner_svc = get_runner_service()
        output_path = payload.get("output_path")
        output_folder = Path(output_path) if output_path else Path.home() / "Collected"

        request = InvokeRequest(
            runner_id=RunnerId.AUTOCOLLECTOR,
            config={"url": url},
            output_folder=str(output_folder),
        )

        # Run synchronously using asyncio
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(runner_svc.invoke(request))
            return {
                "success": result.success,
                "error": result.error,
                "artifacts_count": len(result.artifacts) if result.artifacts else 0,
            }
        finally:
            loop.close()

    def _cmd_start_mail(self) -> dict[str, Any]:
        """Execute start_mail command."""
        from autohelper.modules.mail import MailService

        svc = MailService()
        svc.start()
        return {"started": True}

    def _cmd_stop_mail(self) -> dict[str, Any]:
        """Execute stop_mail command."""
        from autohelper.modules.mail import MailService

        svc = MailService()
        svc.stop()
        return cast(dict[str, Any], {"stopped": True})

    def _cmd_run_gc(self) -> dict[str, Any]:
        """Execute run_gc command."""
        from autohelper.modules.gc.scheduler import trigger_gc_now

        triggered = trigger_gc_now()
        return {"triggered": triggered}

    def _cmd_select_folder(self) -> dict[str, Any]:
        """Execute select_folder command - opens native folder picker dialog."""
        from autohelper.modules.config.router import _open_folder_dialog

        path = _open_folder_dialog()
        return cast(dict[str, Any], {"path": path})

    def _cmd_ping(self) -> dict[str, Any]:
        """Execute ping command — echo back timestamp and version."""
        from datetime import datetime, timezone

        return {
            "pong": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "0.1.0",
        }

    def _cmd_watch_root(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute watch_root command — start watching a root directory."""
        from autohelper.modules.file_watch.router import get_service

        root_id = payload.get("root_id")
        path = payload.get("path")

        if not root_id or not path:
            return {"success": False, "error": "Missing root_id or path"}

        service = get_service()
        success = service.watch(root_id, path)
        return {"success": success}

    def _cmd_unwatch_root(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute unwatch_root command — stop watching a root directory."""
        from autohelper.modules.file_watch.router import get_service

        root_id = payload.get("root_id")

        if not root_id:
            return {"success": False, "error": "Missing root_id"}

        service = get_service()
        success = service.unwatch(root_id)
        return {"success": success}

    def _cmd_execute_manifest(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute execute_manifest command — create tasks in ClickUp from manifest."""
        from autohelper.modules.clickup.manifest import ImportManifest
        from autohelper.modules.clickup.service import execute_manifest

        manifest = ImportManifest.model_validate(payload)

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(execute_manifest(manifest))
            return result.model_dump()
        finally:
            loop.close()

    def _cmd_drain_file_events(self) -> dict[str, Any]:
        """Execute drain_file_events command — return and clear all pending file events."""
        from autohelper.modules.file_watch.router import get_service

        service = get_service()
        events = service.drain_events()
        return {
            "events": [e.model_dump(mode="json") for e in events],
            "count": len(events),
        }

    def _clear_pairing(self) -> None:
        """Clear the local pairing key."""
        store = ConfigStore()
        cfg = store.load()
        cfg.pop("autoart_link_key", None)
        store.save(cfg)
        reset_settings()

        # State transition is handled by caller
        logger.info("Pairing cleared due to invalid link key")

    def _get(self, url: str) -> dict[str, Any]:
        """Make GET request with link key auth."""
        settings = get_settings()
        req = urllib.request.Request(url)
        req.add_header("X-AutoHelper-Key", settings.autoart_link_key)
        req.add_header("Content-Type", "application/json")

        with urllib.request.urlopen(req, timeout=10) as resp:
            return cast(dict[str, Any], json.loads(resp.read()))

    def _post(self, url: str, data: dict[str, Any]) -> dict[str, Any]:
        """Make POST request with link key auth."""
        settings = get_settings()
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("X-AutoHelper-Key", settings.autoart_link_key)
        req.add_header("Content-Type", "application/json")

        with urllib.request.urlopen(req, timeout=10) as resp:
            return cast(dict[str, Any], json.loads(resp.read()))


def start_backend_poller() -> bool:
    """Start the global backend poller."""
    global _poller

    settings = get_settings()

    # Only start if paired
    if not settings.autoart_link_key:
        logger.info("Not paired, backend poller not started")
        return False

    if _poller is not None:
        logger.warning("Backend poller already exists")
        return True

    _poller = BackendPoller()
    _poller.start()
    return True


def stop_backend_poller() -> None:
    """Stop the global backend poller."""
    global _poller

    if _poller is not None:
        _poller.stop()
        _poller = None
