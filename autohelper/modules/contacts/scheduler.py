"""Contact Sync scheduler using APScheduler."""

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from autohelper.config import get_settings

from .service import ContactSyncService

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def get_contact_scheduler() -> AsyncIOScheduler | None:
    """Get the global contact sync scheduler instance."""
    return _scheduler


def get_next_contact_sync_time() -> datetime | None:
    """Get the next scheduled contact sync time."""
    if _scheduler is None:
        return None

    job = _scheduler.get_job("contact_sync")
    if job is None:
        return None

    next_run = job.next_run_time
    if next_run is None:
        return None
    return datetime.fromisoformat(str(next_run)) if not isinstance(next_run, datetime) else next_run


def start_contact_scheduler(service: ContactSyncService | None = None) -> bool:
    """
    Start the contact sync scheduler.

    Returns:
        True if scheduler started, False if disabled
    """
    global _scheduler

    settings = get_settings()

    if not settings.contact_sync_enabled:
        logger.info("Contact sync is disabled, scheduler not started")
        return False

    if service is None:
        service = ContactSyncService()

    if _scheduler is None:
        _scheduler = AsyncIOScheduler()

    # Remove existing job if any
    existing_job = _scheduler.get_job("contact_sync")
    if existing_job:
        _scheduler.remove_job("contact_sync")

    _scheduler.add_job(
        service.run_sync,
        IntervalTrigger(minutes=settings.contact_sync_interval_minutes),
        id="contact_sync",
        name="Contact Sync",
        replace_existing=True,
        next_run_time=datetime.now() + timedelta(minutes=2),  # First run in 2 minutes
    )

    if not _scheduler.running:
        _scheduler.start()
        logger.info(
            "Contact sync scheduler started (interval: %dm, hours: %d-%d %s)",
            settings.contact_sync_interval_minutes,
            settings.contact_sync_work_hours_start,
            settings.contact_sync_work_hours_end,
            settings.contact_sync_timezone,
        )
    else:
        logger.info("Contact sync scheduler job updated")

    return True


def stop_contact_scheduler() -> None:
    """Stop the contact sync scheduler."""
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Contact sync scheduler stopped")

    _scheduler = None
