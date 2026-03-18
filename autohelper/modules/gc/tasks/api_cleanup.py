"""API cleanup tasks for garbage collection."""

import logging

from autohelper.config import get_settings
from autohelper.modules.context.autoart import AutoArtClient

from ..types import APICleanupResult

logger = logging.getLogger(__name__)


def cleanup_import_sessions(
    retention_days: int = 7,
    client: AutoArtClient | None = None,
) -> APICleanupResult:
    """
    Clean up stale import sessions via backend API.

    Args:
        retention_days: Number of days to retain sessions
        client: AutoArtClient instance (default: create from settings)

    Returns:
        APICleanupResult with deletion stats
    """
    result = APICleanupResult(task_name="import_sessions", sessions_deleted=0)

    if client is None:
        settings = get_settings()
        client = AutoArtClient(
            api_url=settings.autoart_api_url,
            link_key=settings.autoart_link_key or None,
        )

    # Check if backend is reachable
    if not client.test_connection():
        error_msg = "Backend not reachable, skipping import session cleanup"
        logger.warning(error_msg)
        result.errors.append(error_msg)
        return result

    try:
        deleted_count, session_ids = client.delete_stale_import_sessions(retention_days)
        result.sessions_deleted = deleted_count
        result.session_ids = session_ids
        logger.info(f"Import session cleanup: deleted {deleted_count} sessions")
    except Exception as e:
        error_msg = f"Error cleaning up import sessions: {e}"
        logger.error(error_msg)
        result.errors.append(error_msg)

    return result


def cleanup_export_sessions(
    retention_days: int = 7,
    client: AutoArtClient | None = None,
) -> APICleanupResult:
    """
    Clean up stale export sessions via backend API.

    Args:
        retention_days: Number of days to retain sessions
        client: AutoArtClient instance (default: create from settings)

    Returns:
        APICleanupResult with deletion stats
    """
    result = APICleanupResult(task_name="export_sessions", sessions_deleted=0)

    if client is None:
        settings = get_settings()
        client = AutoArtClient(
            api_url=settings.autoart_api_url,
            link_key=settings.autoart_link_key or None,
        )

    # Check if backend is reachable
    if not client.test_connection():
        error_msg = "Backend not reachable, skipping export session cleanup"
        logger.warning(error_msg)
        result.errors.append(error_msg)
        return result

    try:
        deleted_count, session_ids = client.delete_stale_export_sessions(retention_days)
        result.sessions_deleted = deleted_count
        result.session_ids = session_ids
        logger.info(f"Export session cleanup: deleted {deleted_count} sessions")
    except Exception as e:
        error_msg = f"Error cleaning up export sessions: {e}"
        logger.error(error_msg)
        result.errors.append(error_msg)

    return result
