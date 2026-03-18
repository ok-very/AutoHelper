"""Garbage Collection scheduler using APScheduler."""

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from autohelper.config import get_settings

from .service import GarbageCollectionService

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler | None:
    """Get the global scheduler instance."""
    return _scheduler


def get_next_run_time() -> datetime | None:
    """Get the next scheduled GC run time."""
    if _scheduler is None:
        return None

    job = _scheduler.get_job("garbage_collection")
    if job is None:
        return None

    next_run = job.next_run_time
    if next_run is None:
        return None
    # Cast to datetime since APScheduler returns Any
    return datetime.fromisoformat(str(next_run)) if not isinstance(next_run, datetime) else next_run


def start_gc_scheduler(gc_service: GarbageCollectionService | None = None) -> bool:
    """
    Start the garbage collection scheduler.

    Args:
        gc_service: GC service instance (default: singleton)

    Returns:
        True if scheduler started, False if disabled
    """
    global _scheduler

    settings = get_settings()

    # Check if GC is enabled
    if not settings.gc_enabled:
        logger.info("Garbage collection is disabled, scheduler not started")
        return False

    if gc_service is None:
        gc_service = GarbageCollectionService()

    # Create scheduler if it doesn't exist
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()

    # Remove existing job if any
    existing_job = _scheduler.get_job("garbage_collection")
    if existing_job:
        _scheduler.remove_job("garbage_collection")

    # Add the GC job
    _scheduler.add_job(
        gc_service.run_cleanup,
        IntervalTrigger(hours=settings.gc_schedule_hours),
        id="garbage_collection",
        name="Garbage Collection",
        replace_existing=True,
        next_run_time=datetime.now() + timedelta(minutes=5),  # First run in 5 minutes
    )

    # Start the scheduler if not running
    if not _scheduler.running:
        _scheduler.start()
        logger.info(
            f"GC scheduler started (interval: {settings.gc_schedule_hours}h, "
            f"retention: {settings.gc_retention_days}d)"
        )
    else:
        logger.info("GC scheduler job updated")

    return True


def stop_gc_scheduler() -> None:
    """Stop the garbage collection scheduler."""
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("GC scheduler stopped")

    _scheduler = None


def trigger_gc_now() -> bool:
    """
    Trigger an immediate GC run outside the schedule.

    Returns:
        True if triggered, False if already running
    """
    gc_service = GarbageCollectionService()

    if gc_service.is_running:
        logger.warning("GC already running, cannot trigger")
        return False

    # Run synchronously (for manual trigger)
    gc_service.run_cleanup()
    return True
