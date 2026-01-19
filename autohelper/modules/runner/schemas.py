"""
Runner module Pydantic schemas for request/response models.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


# =============================================================================
# RUNNER TYPES
# =============================================================================

RunnerId = Literal["autocollector"]


# =============================================================================
# REQUESTS
# =============================================================================

class RunnerInvokeRequest(BaseModel):
    """Request to invoke a runner."""
    runner_id: RunnerId = Field(..., description="Runner identifier")
    config: dict[str, Any] = Field(default_factory=dict, description="Runner-specific config")
    output_folder: str = Field(..., description="Folder to write output artifacts")
    context_id: str | None = Field(None, description="Optional context ID for traceability")
    # Ephemeral key from client (Electron/local) - NOT persisted
    gemini_api_key: str | None = Field(None, description="Optional ephemeral Gemini API key")


# =============================================================================
# PROGRESS & RESULTS
# =============================================================================

class RunnerProgress(BaseModel):
    """Progress update from runner execution."""
    stage: str
    message: str
    percent: int | None = None


class ArtifactRef(BaseModel):
    """Reference to an output artifact."""
    ref_id: str
    path: str
    artifact_type: str  # html, image, pdf, etc.
    mime_type: str | None = None


class RunnerResult(BaseModel):
    """Final result from runner execution."""
    success: bool
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    error: str | None = None
    duration_ms: int | None = None


# =============================================================================
# STATUS
# =============================================================================

class RunnerStatus(BaseModel):
    """Current runner service status."""
    active: bool = False
    current_runner: RunnerId | None = None
    progress: RunnerProgress | None = None
