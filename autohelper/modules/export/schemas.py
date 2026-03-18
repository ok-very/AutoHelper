"""
Export module schemas.
"""

from typing import Any

from pydantic import BaseModel


class IntakeSubmissionData(BaseModel):
    """Submission data from AutoArt API."""

    id: str
    form_id: str
    upload_code: str
    metadata: dict[str, Any]  # Flattened for CSV
    created_at: str


class IntakeCSVExportRequest(BaseModel):
    """Request for intake CSV export."""

    form_id: str
    form_title: str  # Used for filename
    submissions: list[IntakeSubmissionData]
    output_dir: str | None = None  # Optional, defaults to exports/


class IntakeCSVExportResponse(BaseModel):
    """Response from intake CSV export."""

    file_path: str
    row_count: int
    columns: list[str]
