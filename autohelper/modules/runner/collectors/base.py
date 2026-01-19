"""
Base collector interface.
"""

from abc import ABC, abstractmethod
from typing import Any

from autohelper.modules.runner.schemas import ArtifactRef, RunnerProgress


class BaseCollector(ABC):
    """Abstract base class for collectors."""

    @abstractmethod
    async def collect(
        self,
        config: dict[str, Any],
        output_folder: str,
        on_progress: Any,  # Callable[[RunnerProgress], None]
    ) -> list[ArtifactRef]:
        """
        Run collection process.
        
        Args:
            config: Collector-specific configuration
            output_folder: Path to write artifacts
            on_progress: Callback for progress updates
            
        Returns:
            List of generated artifacts
        """
        pass
