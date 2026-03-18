"""
Runner module types - Pydantic models for runner invocation.
Mirrors backend TypeScript types in runner/types.ts.
"""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class RunnerId(str, Enum):
    """Available runner identifiers."""

    AUTOCOLLECTOR = "autocollector"


# =============================================================================
# Naming Configuration
# =============================================================================


class NumberingMode(str, Enum):
    """How to number artifacts during collection."""

    SEQUENTIAL = "sequential"  # Global counter across all sources
    BY_SOURCE = "by_source"  # Separate counter per source URL/path


class CollisionMode(str, Enum):
    """How to handle filename collisions when names match (case-insensitive)."""

    SUFFIX = "suffix"  # Add _1, _2, etc. suffix to avoid collision
    REPLACE = "replace"  # Overwrite existing file (no suffix)


class NamingConfig(BaseModel):
    """
    Configuration for artifact filename generation.

    Template variables:
    - {index}: Sequential number (padded)
    - {hash}: Content/URL hash (8 chars)
    - {date}: Collection date (configurable format)
    - {ext}: File extension from MIME type
    - {artist}: Artist name from page metadata (fallback: "unknown-artist")
    - {title}: Artwork title from alt text/caption (fallback: "untitled-{index}")
    - {source}: Hostname or folder name (fallback: "local")
    """

    template: str = Field(
        default="{index}_{hash}", description="Filename template using {var} placeholders"
    )
    index_start: int = Field(default=1, ge=0, description="Starting index for numbering")
    index_padding: int = Field(default=3, ge=1, le=6, description="Zero-padding width for index")
    prefix: str = Field(default="", description="Prefix prepended to all filenames")
    suffix: str = Field(default="", description="Suffix appended before extension")
    date_format: str = Field(default="%Y%m%d", description="strftime format for {date}")
    numbering_mode: NumberingMode = Field(
        default=NumberingMode.SEQUENTIAL, description="How to count artifacts"
    )
    collision_mode: CollisionMode = Field(
        default=CollisionMode.SUFFIX,
        description="How to handle filename collisions: add suffix or replace",
    )


class RunnerConfig(BaseModel):
    """Configuration for a runner invocation."""

    # Web collection mode
    url: str | None = None

    # Local intake mode
    source_path: str | None = None
    template: str | None = None

    # Allow arbitrary additional config
    class Config:
        extra = "allow"


class InvokeRequest(BaseModel):
    """Request to invoke a runner."""

    runner_id: RunnerId
    config: dict[str, Any]
    output_folder: str = Field(..., min_length=1)
    context_id: str | None = None


class RunnerProgress(BaseModel):
    """Progress update during runner execution."""

    stage: str
    message: str
    percent: int | None = None


class ArtifactRef(BaseModel):
    """Reference to an artifact produced by a runner."""

    ref_id: str
    path: str
    artifact_type: str
    mime_type: str | None = None


class RunnerResult(BaseModel):
    """Result of a runner invocation."""

    success: bool
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    error: str | None = None
    duration_ms: int | None = None


class RunnerStatus(BaseModel):
    """Current status of the runner system."""

    active: bool = False
    current_runner: RunnerId | None = None
    progress: RunnerProgress | None = None


# =============================================================================
# Artifact Manifest Types
# =============================================================================


class ArtifactManifestEntry(BaseModel):
    """
    Persistent metadata for a collected artifact.
    Stored in manifest.json for later retrieval even if file is moved.
    """

    artifact_id: str = Field(..., description="Stable UUID (content-based)")
    original_filename: str = Field(..., description="Filename at collection time")
    current_filename: str = Field(..., description="Current filename (updated if renamed)")
    content_hash: str = Field(..., description="SHA-256 hash for relocation detection")
    source_url: str | None = Field(default=None, description="Source URL if web collection")
    source_path: str | None = Field(default=None, description="Source path if local collection")
    collected_at: str = Field(..., description="ISO timestamp of collection")
    mime_type: str = Field(..., description="Detected MIME type")
    size: int = Field(..., ge=0, description="File size in bytes")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata (dimensions, title, artist, etc.)"
    )


class ExtractedMetadata(BaseModel):
    """
    Metadata extracted from a web page.

    Contains contact info, CV links, and location data extracted
    during collection. Consumed by wizard to populate record fields.
    """

    emails: list[str] = Field(default_factory=list, description="Email addresses found")
    phones: list[str] = Field(default_factory=list, description="Phone numbers found")
    cv_links: list[str] = Field(
        default_factory=list, description="PDF URLs containing cv/resume keywords"
    )
    location: str | None = Field(default=None, description="Best location guess (City, Country)")
    raw_location_candidates: list[str] = Field(
        default_factory=list, description="All location candidates for manual review"
    )


class CollectionManifest(BaseModel):
    """
    Manifest file tracking all artifacts from a collection session.
    Stored at {output_folder}/.artcollector/manifest.json
    """

    manifest_id: str = Field(..., description="Unique ID for this collection")
    version: str = Field(default="1.0", description="Manifest schema version")
    created_at: str = Field(..., description="ISO timestamp of collection start")
    updated_at: str = Field(..., description="ISO timestamp of last update")
    source_type: Literal["web", "local"] = Field(..., description="Collection source type")
    source_url: str | None = Field(default=None, description="Source URL if web collection")
    source_path: str | None = Field(default=None, description="Source path if local collection")
    output_folder: str = Field(..., description="Output folder path")
    naming_config: NamingConfig = Field(
        default_factory=NamingConfig, description="Naming configuration used for this collection"
    )
    artifacts: list[ArtifactManifestEntry] = Field(
        default_factory=list, description="List of collected artifacts"
    )
    extracted_metadata: ExtractedMetadata | None = Field(
        default=None,
        description="Contact info and metadata extracted from source, deployed by wizard to records",
    )
