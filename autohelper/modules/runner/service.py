"""
Runner service implementation.
"""

import asyncio
import threading
import time
from pathlib import Path
from typing import Any, Callable

from autohelper.config import get_settings
from autohelper.modules.reference.schemas import ReferenceCreate
from autohelper.modules.reference.service import ReferenceService
from autohelper.shared.logging import get_logger

from .schemas import RunnerInvokeRequest, RunnerProgress, RunnerResult, RunnerStatus
from .collectors.artist_crawler import ArtistCrawler

logger = get_logger(__name__)


# =============================================================================
# SERVICE
# =============================================================================

class RunnerService:
    """Service for executing external runners/collectors."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.initialized = False
            return cls._instance

    def __init__(self):
        if self.initialized:
            return
        
        self.settings = get_settings()
        self.ref_service = ReferenceService()
        self._active = False
        self._current_runner: str | None = None
        self._progress: RunnerProgress | None = None
        self.initialized = True

    @property
    def status(self) -> RunnerStatus:
        return RunnerStatus(
            active=self._active,
            current_runner=self._current_runner,
            progress=self._progress,
        )

    async def invoke(
        self,
        request: RunnerInvokeRequest,
        on_progress: Callable[[RunnerProgress], None] | None = None,
    ) -> RunnerResult:
        """Invoke a runner/collector."""
        if self._active:
            return RunnerResult(success=False, error="Another runner is already active")

        self._active = True
        self._current_runner = request.runner_id
        start_time = time.time()

        try:
            if request.runner_id == "autocollector":
                # Use native Python implementation
                collector = ArtistCrawler()
                output_folder = self._prepare_output_folder(request.output_folder)
                
                artifacts = await collector.collect(
                    config=request.config,
                    output_folder=str(output_folder),
                    on_progress=self._update_progress_callback(on_progress)
                )
                
                # Register artifacts with ReferenceService
                for artifact in artifacts:
                     self.ref_service.register(ReferenceCreate(
                        path=artifact.path,
                        context_id=request.context_id,
                        work_item_id=request.context_id,
                        note=f"Collector output: {artifact.artifact_type}",
                    ))

                return RunnerResult(success=True, artifacts=artifacts)
            else:
                return RunnerResult(success=False, error=f"Unknown runner: {request.runner_id}")

        except Exception as e:
            logger.exception("Runner failed")
            return RunnerResult(success=False, error=str(e))

        finally:
            if on_progress:
                # Ensure 100% is sent if successful
                pass 
            self._active = False
            self._current_runner = None
            self._progress = None
            
            # Calculate duration
            duration = int((time.time() - start_time) * 1000)

    def _prepare_output_folder(self, folder_path: str) -> Path:
        """Validate and create output folder."""
        path = Path(folder_path).resolve()
        
        # Check allowed roots
        allowed = False
        for root in self.settings.allowed_roots:
            try:
                path.relative_to(root)
                allowed = True
                break
            except ValueError:
                continue
                
        if not allowed:
            raise ValueError(f"Output folder not under allowed roots: {path}")
            
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _update_progress_callback(self, external_callback):
        """Create wrapper to update internal state and call external callback."""
        def wrapper(progress: RunnerProgress):
            self._progress = progress
            if external_callback:
                external_callback(progress)
        return wrapper
