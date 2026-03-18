"""Garbage Collection service - orchestrates cleanup tasks."""

import logging
import threading
from datetime import UTC, datetime

from autohelper.config import Settings, get_settings
from autohelper.modules.context.autoart import AutoArtClient

from .tasks import (
    cleanup_export_sessions,
    cleanup_import_sessions,
    cleanup_mail_ingest,
    cleanup_orphaned_manifests,
    cleanup_rtf_exports,
)
from .types import CleanupResult, GCConfig

logger = logging.getLogger(__name__)


class GarbageCollectionService:
    """
    Service for orchestrating garbage collection tasks.

    This service manages:
    - RTF export cleanup (temp files)
    - Orphaned manifest cleanup (optional)
    - Mail ingest cleanup
    - Backend session cleanup (import/export)

    Usage:
        gc_service = GarbageCollectionService()
        result = gc_service.run_cleanup()
    """

    _instance: "GarbageCollectionService | None" = None
    _lock = threading.Lock()  # Class lock for singleton creation
    _initialized: bool = False

    def __new__(cls) -> "GarbageCollectionService":
        """Singleton pattern with thread safety."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, settings: Settings | None = None) -> None:
        if self._initialized:
            return

        self._settings = settings or get_settings()
        self._config = self._load_config()
        self._last_result: CleanupResult | None = None
        self._last_run: datetime | None = None
        self._running = False
        self._run_lock = threading.Lock()  # Instance lock for run state
        self._client: AutoArtClient | None = None
        self._initialized = True

    def _load_config(self) -> GCConfig:
        """Load GC config from settings."""
        return GCConfig(
            enabled=getattr(self._settings, "gc_enabled", True),
            schedule_hours=getattr(self._settings, "gc_schedule_hours", 24),
            retention_days=getattr(self._settings, "gc_retention_days", 7),
            rtf_temp_path=getattr(self._settings, "gc_rtf_temp_path", None),
            cleanup_orphaned_manifests=getattr(
                self._settings, "gc_cleanup_orphaned_manifests", False
            ),
            cleanup_mail_ingest=getattr(self._settings, "gc_cleanup_mail_ingest", True),
        )

    def _get_client(self) -> AutoArtClient:
        """Get or create AutoArt client."""
        if self._client is None:
            self._client = AutoArtClient(
                api_url=self._settings.autoart_api_url,
                link_key=self._settings.autoart_link_key or None,
            )
        return self._client

    @property
    def enabled(self) -> bool:
        """Check if GC is enabled."""
        return self._config.enabled

    @property
    def last_run(self) -> datetime | None:
        """Get the last run timestamp."""
        return self._last_run

    @property
    def last_result(self) -> CleanupResult | None:
        """Get the last cleanup result."""
        return self._last_result

    @property
    def is_running(self) -> bool:
        """Check if cleanup is currently running."""
        with self._run_lock:
            return self._running

    def run_cleanup(self) -> CleanupResult:
        """
        Run all configured cleanup tasks.

        Returns:
            CleanupResult with aggregated stats from all tasks
        """
        # Use lock to check and set _running atomically
        with self._run_lock:
            if self._running:
                logger.warning("Cleanup already running, skipping")
                return CleanupResult(
                    started_at=datetime.now(UTC),
                    status="failed",
                    errors=["Cleanup already running"],
                )
            self._running = True

        result = CleanupResult(started_at=datetime.now(UTC))

        try:
            logger.info("Starting garbage collection run")

            # 1. RTF Export Cleanup
            try:
                rtf_result = cleanup_rtf_exports(
                    retention_days=self._config.retention_days,
                    temp_path=self._config.rtf_temp_path,
                )
                result.merge_file_result(rtf_result)
            except Exception as e:
                error_msg = f"RTF cleanup failed: {e}"
                logger.error(error_msg)
                result.errors.append(error_msg)

            # 2. Orphaned Manifest Cleanup (if enabled)
            if self._config.cleanup_orphaned_manifests:
                try:
                    manifest_result = cleanup_orphaned_manifests(
                        retention_days=self._config.retention_days,
                    )
                    result.merge_file_result(manifest_result)
                except Exception as e:
                    error_msg = f"Manifest cleanup failed: {e}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)

            # 3. Mail Ingest Cleanup (if enabled)
            if self._config.cleanup_mail_ingest:
                try:
                    mail_result = cleanup_mail_ingest(
                        retention_days=self._config.retention_days,
                    )
                    result.merge_file_result(mail_result)
                except Exception as e:
                    error_msg = f"Mail cleanup failed: {e}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)

            # 4. Backend Session Cleanup
            client = self._get_client()

            try:
                import_result = cleanup_import_sessions(
                    retention_days=self._config.retention_days,
                    client=client,
                )
                result.merge_api_result(import_result)
            except Exception as e:
                error_msg = f"Import session cleanup failed: {e}"
                logger.error(error_msg)
                result.errors.append(error_msg)

            try:
                export_result = cleanup_export_sessions(
                    retention_days=self._config.retention_days,
                    client=client,
                )
                result.merge_api_result(export_result)
            except Exception as e:
                error_msg = f"Export session cleanup failed: {e}"
                logger.error(error_msg)
                result.errors.append(error_msg)

            result.status = "completed"
            result.completed_at = datetime.now(UTC)
            self._last_result = result
            self._last_run = result.started_at

            logger.info(
                f"Garbage collection completed: "
                f"RTF={result.rtf_files_deleted}, "
                f"manifests={result.manifests_cleaned}, "
                f"mail={result.mail_files_deleted}, "
                f"import_sessions={result.import_sessions_deleted}, "
                f"export_sessions={result.export_sessions_deleted}"
            )

        except Exception as e:
            error_msg = f"Garbage collection run failed: {e}"
            logger.error(error_msg)
            result.status = "failed"
            result.completed_at = datetime.now(UTC)
            result.errors.append(error_msg)
            self._last_result = result

        finally:
            with self._run_lock:
                self._running = False

        return result

    def reload_config(self) -> None:
        """Reload configuration from settings."""
        self._settings = get_settings()
        self._config = self._load_config()
        self._client = None  # Reset client to pick up new settings
        logger.info("GC config reloaded")
