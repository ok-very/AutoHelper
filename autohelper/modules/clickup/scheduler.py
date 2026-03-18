"""ClickUp template sync scheduler using APScheduler."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from autohelper.config import get_settings

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def get_clickup_scheduler() -> AsyncIOScheduler | None:
    """Get the global ClickUp sync scheduler instance."""
    return _scheduler


def get_next_sync_time() -> datetime | None:
    """Get the next scheduled template sync time."""
    if _scheduler is None:
        return None

    job = _scheduler.get_job("clickup_template_sync")
    if job is None:
        return None

    next_run = job.next_run_time
    if next_run is None:
        return None
    return (
        datetime.fromisoformat(str(next_run))
        if not isinstance(next_run, datetime)
        else next_run
    )


async def _run_sync() -> None:
    """Run template sync (called by scheduler)."""
    from .template_sync import sync_template

    try:
        report = await sync_template(force=True)
        logger.info(
            "Scheduled template sync complete: %d creates, %d updates",
            len(report.creates),
            len(report.updates),
        )
    except Exception:
        logger.exception("Scheduled template sync failed")


def start_clickup_scheduler() -> bool:
    """Start the ClickUp template sync scheduler."""
    global _scheduler

    settings = get_settings()

    if not getattr(settings, "clickup_sync_enabled", False):
        logger.info("ClickUp template sync disabled, scheduler not started")
        return False

    if not getattr(settings, "clickup_token", ""):
        logger.info("ClickUp token not configured, scheduler not started")
        return False

    interval_hours = getattr(settings, "clickup_sync_interval_hours", 6)

    if _scheduler is None:
        _scheduler = AsyncIOScheduler()

    existing = _scheduler.get_job("clickup_template_sync")
    if existing:
        _scheduler.remove_job("clickup_template_sync")

    _scheduler.add_job(
        _run_sync,
        IntervalTrigger(hours=interval_hours),
        id="clickup_template_sync",
        name="ClickUp Template Sync",
        replace_existing=True,
        next_run_time=datetime.now() + timedelta(minutes=5),
    )

    if not _scheduler.running:
        _scheduler.start()
        logger.info(
            "ClickUp template sync scheduler started (interval: %dh)",
            interval_hours,
        )
    else:
        logger.info("ClickUp template sync scheduler job updated")

    return True


def stop_clickup_scheduler() -> None:
    """Stop the ClickUp template sync scheduler."""
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("ClickUp template sync scheduler stopped")

    _scheduler = None
