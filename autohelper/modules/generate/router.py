"""
Generate module router.
"""

from fastapi import APIRouter, Depends, HTTPException

from autohelper.shared.errors import NotFoundError
from .schemas import ArtifactResponse, IntakeManifestRequest, ReportRequest
from .service import GenerateService

router = APIRouter(prefix="/generate", tags=["generate"])


def get_service() -> GenerateService:
    """Dependency injection for service."""
    return GenerateService()


@router.post("/intake-manifest", response_model=ArtifactResponse)
def generate_intake_manifest(
    req: IntakeManifestRequest,
    service: GenerateService = Depends(get_service)
) -> ArtifactResponse:
    """Generate an intake manifest for a folder."""
    try:
        return service.generate_intake_manifest(req)
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/report", response_model=ArtifactResponse)
def generate_report(
    req: ReportRequest,
    service: GenerateService = Depends(get_service)
) -> ArtifactResponse:
    """Generate a report artifact."""
    try:
        return service.generate_report(req)
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
