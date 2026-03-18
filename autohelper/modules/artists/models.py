"""
Pydantic v2 models for artist_manifest.json schema.

Generalized from BFA-artist-lists to support multi-category artist records
with flexible identity tagging.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Identity sub-models
# ---------------------------------------------------------------------------

class NameEntry(BaseModel):
    """A typed name (traditional, pseudonym, studio, trade)."""

    name: str
    type: str = "pseudonym"  # "traditional", "pseudonym", "studio", "trade"


class AffiliationEntry(BaseModel):
    """A typed affiliation (nation, collective, duo_partner, etc.)."""

    name: str
    type: str = "nation"  # "nation", "collective", "duo_partner", "studio_assistant_of", "band", "organization"


class LocationEntry(BaseModel):
    """A typed location (origin, home, studio)."""

    place: str
    type: str = "origin"  # "origin", "home", "studio"


class IdentityTags(BaseModel):
    """Self-identified characteristics and affiliations."""

    identities: list[str] = Field(default_factory=list)
    affiliations: list[AffiliationEntry] = Field(default_factory=list)
    locations: list[LocationEntry] = Field(default_factory=list)


class Identity(BaseModel):
    display_name: str
    first_name: str | None = None
    last_name: str | None = None
    names: list[NameEntry] = Field(default_factory=list)
    pronouns: str | None = None
    career_stage: str | None = None  # "emerging", "mid-career", "established"
    identity_tags: IdentityTags = Field(default_factory=IdentityTags)


# ---------------------------------------------------------------------------
# Contact / Folder / Document
# ---------------------------------------------------------------------------

class Contact(BaseModel):
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    notes: str | None = None


class FolderLocation(BaseModel):
    """One physical folder containing this artist's files."""

    category: str  # "indigenous", "public", "private", "corporate"
    folder_path: str
    nation: str | None = None
    is_primary: bool = True


class DocumentEntry(BaseModel):
    file_path: str
    date: str | None = None
    is_current: bool = True


class Documents(BaseModel):
    bios: list[DocumentEntry] = Field(default_factory=list)
    cvs: list[DocumentEntry] = Field(default_factory=list)
    tearsheets: list[DocumentEntry] = Field(default_factory=list)
    project_lists: list[DocumentEntry] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Engagement
# ---------------------------------------------------------------------------

class PanelEntry(BaseModel):
    date: str | None = None
    project: str | None = None
    role: str = "selection_panel"  # "selection_panel", "community_advisor", "cultural_advisor", "juror"


class EOIEntry(BaseModel):
    project_name: str | None = None
    folder_path: str | None = None
    file_path: str | None = None


class ConceptProposal(BaseModel):
    project_name: str | None = None
    developer: str | None = None
    date: str | None = None
    folder_path: str | None = None
    file_path: str | None = None


class PublicArtProject(BaseModel):
    project_name: str
    developer: str | None = None
    role: str | None = None
    status: str = "submitted"  # "submitted", "longlisted", "shortlisted", "awarded", "completed"
    year: str | None = None
    status_date: str | None = None
    eoi_ref: str | None = None


class Engagement(BaseModel):
    panel_count: int = 0
    panel_history: list[PanelEntry] = Field(default_factory=list)
    public_art_projects: list[PublicArtProject] = Field(default_factory=list)
    eois: list[EOIEntry] = Field(default_factory=list)
    concept_proposals: list[ConceptProposal] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Images / Completeness
# ---------------------------------------------------------------------------

class Images(BaseModel):
    count: int = 0
    folder_paths: list[str] = Field(default_factory=list)


class Completeness(BaseModel):
    has_bio: bool = False
    has_cv: bool = False
    has_tearsheet: bool = False
    has_contact_email: bool = False
    has_contact_phone: bool = False
    has_website: bool = False
    has_images: bool = False
    has_pronouns: bool = False
    score: float = 0.0
    gaps: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

class ArtistManifest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    artist_id: str
    manifest_version: str = "3.0"
    generated_at: str
    categories: list[str] = Field(default_factory=list)
    identity: Identity
    contact: Contact = Field(default_factory=Contact)
    folder_locations: list[FolderLocation] = Field(default_factory=list)
    documents: Documents = Field(default_factory=Documents)
    engagement: Engagement = Field(default_factory=Engagement)
    images: Images = Field(default_factory=Images)
    completeness: Completeness = Field(default_factory=Completeness)
    review_notes: list[str] = Field(
        default_factory=list,
        serialization_alias="_review_notes",
        validation_alias="_review_notes",
    )

    def model_dump_json_friendly(self) -> dict:
        """Return dict with _review_notes key for JSON serialisation."""
        return self.model_dump(by_alias=True)


class ReferenceManifest(BaseModel):
    """Lightweight stub written to secondary folders pointing to the primary."""

    manifest_type: str = "reference"
    artist_id: str
    primary_folder: str
    primary_category: str
    display_name: str
    generated_at: str
