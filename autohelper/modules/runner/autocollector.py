"""
AutoCollector Runner - Web scraping and local folder intake.

Orchestrates artifact collection from web URLs and local folders.
Delegates to specialized collectors for each source type.
"""

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from autohelper.config.store import ConfigStore
from autohelper.shared.logging import get_logger

from .collectors import FolderCollector, WebCollector
from .service import BaseRunner
from .types import NamingConfig, RunnerId, RunnerProgress, RunnerResult

logger = get_logger(__name__)

DEFAULT_CRAWL_DEPTH = 20


def _safe_int(val: Any, default: int) -> int:
    """Safely coerce a value to int, returning default on failure."""
    if val is None:
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


class AutoCollectorRunner(BaseRunner):
    """
    AutoCollector runner for web scraping and local folder intake.

    Modes:
    - Web: Provide 'url' in config to scrape a website
    - Local: Provide 'source_path' in config to scan a folder

    The runner delegates to specialized collectors:
    - WebCollector for web URLs
    - FolderCollector for local paths

    Supports naming configuration for generated filenames and
    creates manifests for artifact tracking.
    """

    def __init__(self) -> None:
        """Initialize the collector with web and folder handlers."""
        self._config_store = ConfigStore()
        self._folder_collector = FolderCollector()

    async def _get_web_collector(self) -> WebCollector:
        """Create WebCollector with current settings from config."""
        config = await asyncio.to_thread(self._config_store.load)
        return WebCollector(
            max_images=_safe_int(config.get("crawl_depth"), DEFAULT_CRAWL_DEPTH),
            min_width=_safe_int(config.get("min_width"), 100),
            max_width=_safe_int(config.get("max_width"), 5000),
            min_height=_safe_int(config.get("min_height"), 100),
            max_height=_safe_int(config.get("max_height"), 5000),
            min_filesize_kb=_safe_int(config.get("min_filesize_kb"), 100),
            max_filesize_kb=_safe_int(config.get("max_filesize_kb"), 12000),
        )

    @property
    def runner_id(self) -> RunnerId:
        return RunnerId.AUTOCOLLECTOR

    async def invoke(
        self,
        config: dict[str, Any],
        output_folder: Path,
        context_id: str | None = None,
    ) -> RunnerResult:
        """
        Execute the collector.

        Args:
            config: Configuration dict with either 'url' or 'source_path'
            output_folder: Output folder for collected artifacts
            context_id: Optional context identifier

        Returns:
            RunnerResult with collection outcome
        """
        # Validate config is a dict
        if not isinstance(config, dict):
            return RunnerResult(
                success=False,
                error="Config must be a dictionary",
            )

        # Parse naming config with validation error handling
        try:
            naming_config = NamingConfig(**(config.get("naming_config") or {}))
        except ValidationError as e:
            return RunnerResult(
                success=False,
                error=f"Invalid naming_config: {e}",
            )

        url = config.get("url")
        source_path = config.get("source_path")

        try:
            if url:
                web_collector = await self._get_web_collector()
                return await web_collector.collect(url, output_folder, naming_config, context_id)
            elif source_path:
                return await self._folder_collector.collect(
                    source_path, output_folder, naming_config, context_id
                )
            else:
                return RunnerResult(
                    success=False,
                    error="Config must include 'url' or 'source_path'",
                )
        except Exception as e:
            logger.exception(f"Collector failed: {e}")
            return RunnerResult(
                success=False,
                error=f"Collector error: {e}",
            )

    async def invoke_stream(
        self,
        config: dict[str, Any],
        output_folder: Path,
        context_id: str | None = None,
    ) -> AsyncIterator[RunnerProgress]:
        """
        Execute with streaming progress.

        Args:
            config: Configuration dict with either 'url' or 'source_path'
            output_folder: Output folder for collected artifacts
            context_id: Optional context identifier

        Yields:
            RunnerProgress events during collection
        """
        # Validate config is a dict
        if not isinstance(config, dict):
            yield RunnerProgress(
                stage="error",
                message="Config must be a dictionary",
            )
            return

        # Parse naming config with validation error handling
        try:
            naming_config = NamingConfig(**(config.get("naming_config") or {}))
        except ValidationError as e:
            yield RunnerProgress(
                stage="error",
                message=f"Invalid naming_config: {e}",
            )
            return

        url = config.get("url")
        source_path = config.get("source_path")

        try:
            if url:
                web_collector = await self._get_web_collector()
                async for progress in web_collector.collect_stream(
                    url, output_folder, naming_config, context_id
                ):
                    yield progress
            elif source_path:
                async for progress in self._folder_collector.collect_stream(
                    source_path, output_folder, naming_config, context_id
                ):
                    yield progress
            else:
                yield RunnerProgress(
                    stage="error",
                    message="Config must include 'url' or 'source_path'",
                )
        except Exception as e:
            logger.exception(f"Collector stream failed: {e}")
            yield RunnerProgress(
                stage="error",
                message=f"Collector error: {e}",
            )
