"""
Generate module schemas.
"""

from typing import Any
from pydantic import BaseModel


class IntakeManifestRequest(BaseModel):
    """Request to generate an intake manifest."""
    context_id: str
    intake_folder: str
    options: dict[str, Any] | None = None


class ReportRequest(BaseModel):
    """Request to generate a report artifact."""
    context_id: str
    template: str
    payload: dict[str, Any]
    options: dict[str, Any] | None = None


class ArtifactResponse(BaseModel):
    """Response after generating an artifact."""
    ref_id: str
    path: str
    artifact_type: str
