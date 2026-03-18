"""
Export module API router.
"""

import asyncio

from fastapi import APIRouter

from .schemas import IntakeCSVExportRequest, IntakeCSVExportResponse
from .service import ExportService

router = APIRouter(prefix="/export", tags=["export"])


@router.post("/intake-csv", response_model=IntakeCSVExportResponse)
async def export_intake_csv(request: IntakeCSVExportRequest) -> IntakeCSVExportResponse:
    """
    Export intake form submissions to CSV.

    Submissions data should be provided in the request body.
    Returns the path to the generated CSV file.
    """
    service = ExportService()

    file_path, row_count, columns = await asyncio.to_thread(
        service.export_intake_csv,
        form_id=request.form_id,
        form_title=request.form_title,
        submissions=request.submissions,
        output_dir=request.output_dir,
    )

    return IntakeCSVExportResponse(
        file_path=file_path,
        row_count=row_count,
        columns=columns,
    )
