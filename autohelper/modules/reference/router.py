"""
Reference module API router.
"""

from fastapi import APIRouter

from .schemas import ReferenceCreate, ReferenceDTO, ResolveRequest, ResolutionResult
from .service import ReferenceService

router = APIRouter(prefix="/refs", tags=["references"])

@router.post("/register", response_model=ReferenceDTO)
async def register(req: ReferenceCreate) -> ReferenceDTO:
    """Register a new reference."""
    service = ReferenceService()
    return service.register(req)

@router.post("/resolve", response_model=ResolutionResult)
async def resolve(req: ResolveRequest) -> ResolutionResult:
    """Resolve a reference to a path."""
    service = ReferenceService()
    return service.resolve(req.ref_id)
