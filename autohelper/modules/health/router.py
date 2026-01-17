"""Health module routes."""

from fastapi import APIRouter

from .schemas import HealthResponse, StatusResponse
from .service import HealthService

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """
    Simple health check.
    
    Returns ok if the service is running.
    """
    service = HealthService()
    return service.get_health()


@router.get("/status", response_model=StatusResponse)
async def status() -> StatusResponse:
    """
    Detailed status check.
    
    Returns:
    - Database connectivity
    - Migration status
    - Configured roots and their accessibility
    - Last index run info
    """
    service = HealthService()
    return service.get_status()
