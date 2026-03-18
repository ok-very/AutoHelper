"""
Runner service - orchestrates runner execution.
"""

import asyncio
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from autohelper.shared.logging import get_logger

from .types import (
    InvokeRequest,
    RunnerId,
    RunnerProgress,
    RunnerResult,
    RunnerStatus,
)

logger = get_logger(__name__)


class BaseRunner(ABC):
    """Abstract base class for runners."""

    @property
    @abstractmethod
    def runner_id(self) -> RunnerId:
        """The unique identifier for this runner."""
        ...

    @abstractmethod
    async def invoke(
        self,
        config: dict[str, Any],
        output_folder: Path,
        context_id: str | None = None,
    ) -> RunnerResult:
        """Execute the runner synchronously."""
        ...

    @abstractmethod
    def invoke_stream(
        self,
        config: dict[str, Any],
        output_folder: Path,
        context_id: str | None = None,
    ) -> AsyncIterator[RunnerProgress]:
        """Execute the runner with streaming progress updates."""
        ...


class RunnerService:
    """
    Service for managing and executing runners.
    Maintains a registry of available runners and tracks execution state.
    """

    def __init__(self) -> None:
        self._runners: dict[RunnerId, BaseRunner] = {}
        self._active: bool = False
        self._current_runner: RunnerId | None = None
        self._current_progress: RunnerProgress | None = None
        self._lock = asyncio.Lock()  # Protect concurrent access to state

    def register(self, runner: BaseRunner) -> None:
        """Register a runner with the service."""
        self._runners[runner.runner_id] = runner
        logger.info(f"Registered runner: {runner.runner_id}")

    def get_runner(self, runner_id: RunnerId) -> BaseRunner | None:
        """Get a runner by ID."""
        return self._runners.get(runner_id)

    def list_runners(self) -> list[str]:
        """List all registered runner IDs."""
        return [r.value for r in self._runners]

    def get_status(self) -> RunnerStatus:
        """Get current runner status."""
        return RunnerStatus(
            active=self._active,
            current_runner=self._current_runner,
            progress=self._current_progress,
        )

    async def invoke(self, request: InvokeRequest) -> RunnerResult:
        """
        Invoke a runner.

        Args:
            request: The invocation request

        Returns:
            RunnerResult with success status and artifacts
        """
        runner = self._runners.get(request.runner_id)
        if not runner:
            return RunnerResult(
                success=False,
                error=f"Runner '{request.runner_id}' not found",
            )

        # Acquire lock to prevent concurrent invocations from corrupting state
        async with self._lock:
            if self._active:
                return RunnerResult(
                    success=False,
                    error="Another runner is already active",
                )

            # Track state
            self._active = True
            self._current_runner = request.runner_id
            self._current_progress = RunnerProgress(
                stage="starting",
                message="Initializing runner...",
                percent=0,
            )

            start_time = time.perf_counter()

            try:
                output_path = Path(request.output_folder)
                result = await runner.invoke(
                    config=request.config,
                    output_folder=output_path,
                    context_id=request.context_id,
                )

                # Add duration
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                result.duration_ms = duration_ms

                return result

            except Exception as e:
                logger.exception(f"Runner {request.runner_id} failed")
                return RunnerResult(
                    success=False,
                    error=str(e),
                    duration_ms=int((time.perf_counter() - start_time) * 1000),
                )
            finally:
                self._active = False
                self._current_runner = None
                self._current_progress = None

    async def invoke_stream(self, request: InvokeRequest) -> AsyncIterator[RunnerProgress]:
        """
        Invoke a runner with streaming progress.

        Args:
            request: The invocation request

        Yields:
            RunnerProgress updates
        """
        runner = self._runners.get(request.runner_id)
        if not runner:
            yield RunnerProgress(
                stage="error",
                message=f"Runner '{request.runner_id}' not found",
            )
            return

        # Acquire lock to check and set state atomically
        await self._lock.acquire()
        if self._active:
            self._lock.release()
            yield RunnerProgress(
                stage="error",
                message="Another runner is already active",
            )
            return

        self._active = True
        self._current_runner = request.runner_id
        self._lock.release()

        try:
            output_path = Path(request.output_folder)
            async for progress in runner.invoke_stream(
                config=request.config,
                output_folder=output_path,
                context_id=request.context_id,
            ):
                self._current_progress = progress
                yield progress

        except Exception as e:
            logger.exception(f"Runner {request.runner_id} failed")
            yield RunnerProgress(
                stage="error",
                message=str(e),
            )
        finally:
            async with self._lock:
                self._active = False
                self._current_runner = None
                self._current_progress = None


# Global service instance
_runner_service: RunnerService | None = None


def get_runner_service() -> RunnerService:
    """Get or create the global runner service."""
    global _runner_service
    if _runner_service is None:
        _runner_service = RunnerService()
        # Register default runners
        from .autocollector import AutoCollectorRunner

        _runner_service.register(AutoCollectorRunner())
    return _runner_service
