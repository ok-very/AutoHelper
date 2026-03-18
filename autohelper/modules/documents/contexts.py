"""Validated data contracts for document rendering."""

from pydantic import BaseModel


class SubmissionReportRow(BaseModel):
    artist_name: str = ""
    title: str = ""
    location_text: str = ""
    image_path: str = ""
    thumb_url: str | None = None
    width_px: int | None = None
    height_px: int | None = None
    file_bytes: int | None = None
    floor: list[str] = []
    category: list[str] = []
    selected_dpis: list[str] = []
    rank: int = 0
    confirmed: bool = False
    tiers: dict[str, tuple[float, float]] = {}  # tier_id -> (w_in, h_in)


class SubmissionReportContext(BaseModel):
    """V1 render context for submission report."""
    version: int = 1
    manifest_id: str
    manifest_name: str
    generated_at: str
    rows: list[SubmissionReportRow]
    tier_labels: dict[str, str] = {}  # tier_id -> label
