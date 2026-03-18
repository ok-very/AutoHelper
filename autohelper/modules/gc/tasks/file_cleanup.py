"""File cleanup tasks for garbage collection."""

import logging
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from autohelper.config import get_settings

from ..types import FileCleanupResult

logger = logging.getLogger(__name__)


def cleanup_rtf_exports(
    retention_days: int = 7,
    temp_path: str | None = None,
) -> FileCleanupResult:
    """
    Clean up old RTF export files from temp directory.

    RTF exports are created with pattern: bfa_todo_*.rtf
    Files older than retention_days are deleted.

    Args:
        retention_days: Number of days to retain files
        temp_path: Custom temp path (default: system temp)

    Returns:
        FileCleanupResult with deletion stats
    """
    result = FileCleanupResult(task_name="rtf_cleanup", files_deleted=0, bytes_freed=0)

    # Use system temp if not specified
    if temp_path is None:
        temp_path = tempfile.gettempdir()

    temp_dir = Path(temp_path)
    if not temp_dir.exists():
        logger.warning(f"RTF temp path does not exist: {temp_path}")
        return result

    cutoff_time = datetime.now() - timedelta(days=retention_days)
    cutoff_timestamp = cutoff_time.timestamp()

    # Find RTF files matching the pattern
    pattern = "bfa_todo_*.rtf"
    try:
        for rtf_file in temp_dir.glob(pattern):
            try:
                stat = rtf_file.stat()
                if stat.st_mtime < cutoff_timestamp:
                    file_size = stat.st_size
                    rtf_file.unlink()
                    result.files_deleted += 1
                    result.bytes_freed += file_size
                    logger.debug(f"Deleted stale RTF: {rtf_file.name}")
            except OSError as e:
                error_msg = f"Failed to delete {rtf_file}: {e}"
                logger.warning(error_msg)
                result.errors.append(error_msg)
    except Exception as e:
        error_msg = f"Error scanning RTF files: {e}"
        logger.error(error_msg)
        result.errors.append(error_msg)

    logger.info(
        f"RTF cleanup: deleted {result.files_deleted} files, freed {result.bytes_freed} bytes"
    )
    return result


def cleanup_orphaned_manifests(
    retention_days: int = 7,
    allowed_roots: list[str] | None = None,
) -> FileCleanupResult:
    """
    Clean up orphaned .artcollector manifest directories.

    An orphaned manifest is one where:
    - The parent directory contains no image/media files
    - The manifest is older than retention_days

    This is a risky operation and should only be run with explicit user consent.

    Args:
        retention_days: Number of days to retain manifests
        allowed_roots: List of root paths to scan (default: from settings)

    Returns:
        FileCleanupResult with deletion stats
    """
    result = FileCleanupResult(task_name="manifest_cleanup", files_deleted=0, bytes_freed=0)

    settings = get_settings()
    if allowed_roots is None:
        allowed_roots = settings.allowed_roots

    if not allowed_roots:
        logger.info("No allowed roots configured, skipping manifest cleanup")
        return result

    cutoff_time = datetime.now() - timedelta(days=retention_days)
    cutoff_timestamp = cutoff_time.timestamp()

    # Image/media extensions to check for
    media_extensions = {
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp",
        ".mp4", ".mov", ".avi", ".mkv", ".mp3", ".wav", ".flac",
    }

    for root_path in allowed_roots:
        root = Path(root_path)
        if not root.exists():
            continue

        # Find .artcollector directories
        try:
            for manifest_dir in root.rglob(".artcollector"):
                if not manifest_dir.is_dir():
                    continue

                try:
                    # Check manifest age
                    manifest_mtime = manifest_dir.stat().st_mtime
                    if manifest_mtime >= cutoff_timestamp:
                        continue  # Not old enough

                    # Check if parent has media files
                    parent = manifest_dir.parent
                    has_media = False
                    for item in parent.iterdir():
                        if item.is_file() and item.suffix.lower() in media_extensions:
                            has_media = True
                            break

                    if not has_media:
                        # Orphaned manifest - delete it
                        files = [f for f in manifest_dir.rglob("*") if f.is_file()]
                        bytes_freed = sum(f.stat().st_size for f in files)

                        try:
                            shutil.rmtree(manifest_dir)
                            result.files_deleted += 1
                            result.bytes_freed += bytes_freed
                            logger.debug(f"Deleted orphaned manifest: {manifest_dir}")
                        except OSError as rm_err:
                            error_msg = f"Failed to remove {manifest_dir}: {rm_err}"
                            logger.warning(error_msg)
                            result.errors.append(error_msg)

                except OSError as e:
                    error_msg = f"Failed to process manifest {manifest_dir}: {e}"
                    logger.warning(error_msg)
                    result.errors.append(error_msg)

        except Exception as e:
            error_msg = f"Error scanning root {root_path}: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)

    logger.info(
        f"Manifest cleanup: deleted {result.files_deleted} dirs, "
        f"freed {result.bytes_freed} bytes"
    )
    return result


def cleanup_mail_ingest(
    retention_days: int = 7,
    mail_ingest_path: Path | None = None,
) -> FileCleanupResult:
    """
    Clean up processed mail files from ingest directory.

    Deletes .pst and other processed mail files older than retention_days.

    Args:
        retention_days: Number of days to retain files
        mail_ingest_path: Custom ingest path (default: from settings)

    Returns:
        FileCleanupResult with deletion stats
    """
    result = FileCleanupResult(task_name="mail_cleanup", files_deleted=0, bytes_freed=0)

    settings = get_settings()
    if mail_ingest_path is None:
        mail_ingest_path = settings.mail_ingest_path

    if not mail_ingest_path.exists():
        logger.info(f"Mail ingest path does not exist: {mail_ingest_path}")
        return result

    cutoff_time = datetime.now() - timedelta(days=retention_days)
    cutoff_timestamp = cutoff_time.timestamp()

    # Mail file extensions to clean up
    mail_extensions = {".pst", ".ost", ".mbox", ".eml"}

    try:
        for mail_file in mail_ingest_path.iterdir():
            if not mail_file.is_file():
                continue

            if mail_file.suffix.lower() not in mail_extensions:
                continue

            try:
                stat = mail_file.stat()
                if stat.st_mtime < cutoff_timestamp:
                    file_size = stat.st_size
                    mail_file.unlink()
                    result.files_deleted += 1
                    result.bytes_freed += file_size
                    logger.debug(f"Deleted stale mail file: {mail_file.name}")
            except OSError as e:
                error_msg = f"Failed to delete {mail_file}: {e}"
                logger.warning(error_msg)
                result.errors.append(error_msg)

    except Exception as e:
        error_msg = f"Error scanning mail ingest: {e}"
        logger.error(error_msg)
        result.errors.append(error_msg)

    logger.info(
        f"Mail cleanup: deleted {result.files_deleted} files, freed {result.bytes_freed} bytes"
    )
    return result
