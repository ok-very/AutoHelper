from enum import Enum

from pydantic import BaseModel, Field


class ContextLayerType(str, Enum):
    CONTEXT_ART = "context_art"
    PARKS = "parks"
    SCHOOLS = "schools"
    COMMUNITY_CENTRES = "community_centres"
    SITE = "site"


class ContextArtwork(BaseModel):
    """A specific artwork referenced in the project's PUBLIC ART CONTEXT section."""
    number: int  # legend number (1-based)
    artist: str
    title: str
    year: int | None = None
    address: str  # geocodeable address


class ContextMapRequest(BaseModel):
    project_slug: str
    site_address: str
    site_label: str = ""
    municipality: str = ""
    radius_km: float = Field(default=1.0, ge=0.1, le=50.0)
    context_artworks: list[ContextArtwork] = Field(default_factory=list)
    layers: list[ContextLayerType] = Field(
        default_factory=lambda: [
            ContextLayerType.CONTEXT_ART,
            ContextLayerType.PARKS,
            ContextLayerType.SCHOOLS,
            ContextLayerType.COMMUNITY_CENTRES,
        ]
    )


class ContextMapResult(BaseModel):
    map_id: str
    map_url: str
    thumbnail_url: str | None = None
    layers: dict[str, str] = Field(default_factory=dict)
    project_slug: str


class StaticMapResult(BaseModel):
    output_path: str
    project_slug: str
    legend: dict[str, list[dict[str, str]]] = Field(default_factory=dict)
