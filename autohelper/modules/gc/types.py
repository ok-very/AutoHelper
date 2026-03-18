"""Garbage Collection types and data classes."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass
class GCConfig:
    """Configuration for garbage collection."""

    enabled: bool = True
    schedule_hours: int = 24  # Run daily
    retention_days: int = 7
    rtf_temp_path: str | None = None  # Auto-detect OS temp
    cleanup_orphaned_manifests: bool = False  # Disabled by default (risky)
    cleanup_mail_ingest: bool = True


@dataclass
class FileCleanupResult:
    """Result of a file cleanup task."""

    task_name: str
    files_deleted: int
    bytes_freed: int
    errors: list[str] = field(default_factory=list)


@dataclass
class APICleanupResult:
    """Result of an API cleanup task."""

    task_name: str
    sessions_deleted: int
    session_ids: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class CleanupResult:
    """Aggregated result of all cleanup tasks."""

    started_at: datetime
    completed_at: datetime | None = None
    status: Literal["running", "completed", "failed"] = "running"
    rtf_files_deleted: int = 0
    rtf_bytes_freed: int = 0
    manifests_cleaned: int = 0
    mail_files_deleted: int = 0
    import_sessions_deleted: int = 0
    export_sessions_deleted: int = 0
    errors: list[str] = field(default_factory=list)

    def merge_file_result(self, result: FileCleanupResult) -> None:
        """Merge a file cleanup result into this aggregate."""
        if result.task_name == "rtf_cleanup":
            self.rtf_files_deleted += result.files_deleted
            self.rtf_bytes_freed += result.bytes_freed
        elif result.task_name == "manifest_cleanup":
            self.manifests_cleaned += result.files_deleted
        elif result.task_name == "mail_cleanup":
            self.mail_files_deleted += result.files_deleted
        self.errors.extend(result.errors)

    def merge_api_result(self, result: APICleanupResult) -> None:
        """Merge an API cleanup result into this aggregate."""
        if result.task_name == "import_sessions":
            self.import_sessions_deleted += result.sessions_deleted
        elif result.task_name == "export_sessions":
            self.export_sessions_deleted += result.sessions_deleted
        self.errors.extend(result.errors)
