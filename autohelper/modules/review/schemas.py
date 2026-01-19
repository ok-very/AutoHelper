"""
Review module Pydantic schemas for Gemini AI review/repair.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


# =============================================================================
# REVIEW TYPES
# =============================================================================

ReviewType = Literal["grammar", "structure", "full"]


# =============================================================================
# PATCH SUGGESTIONS
# =============================================================================

class PatchLocation(BaseModel):
    """Location of a suggested patch."""
    start_line: int | None = None
    end_line: int | None = None
    start_char: int | None = None
    end_char: int | None = None
    selector: str | None = None  # CSS selector for HTML


class PatchSuggestion(BaseModel):
    """A single suggested patch from AI review."""
    id: str
    category: str  # grammar, structure, content, formatting
    severity: Literal["info", "warning", "error"]
    location: PatchLocation | None = None
    original_text: str | None = None
    suggested_text: str | None = None
    explanation: str


# =============================================================================
# REQUESTS
# =============================================================================

class ReviewRequest(BaseModel):
    """Request to analyze an artifact with AI."""
    artifact_path: str = Field(..., description="Path to artifact to review")
    review_type: ReviewType = Field(default="full", description="Type of review")
    context_id: str | None = None
    # Ephemeral key - NOT persisted, NOT logged
    gemini_api_key: str | None = Field(None, description="Optional ephemeral Gemini API key")


class ApplyPatchesRequest(BaseModel):
    """Request to apply approved patches."""
    artifact_path: str
    patch_ids: list[str] = Field(..., description="IDs of patches to apply")
    context_id: str | None = None


# =============================================================================
# RESPONSES
# =============================================================================

class ReviewResult(BaseModel):
    """Result of AI review."""
    success: bool
    patches: list[PatchSuggestion] = Field(default_factory=list)
    summary: str | None = None
    error: str | None = None


class ApplyPatchesResult(BaseModel):
    """Result of applying patches."""
    success: bool
    applied_count: int = 0
    output_path: str | None = None
    error: str | None = None
