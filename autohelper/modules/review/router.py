"""
Review module API routes.
"""

from fastapi import APIRouter

from autohelper.shared.logging import get_logger

from .schemas import (
    ApplyPatchesRequest,
    ApplyPatchesResult,
    ReviewRequest,
    ReviewResult,
)
from .service import ReviewService

logger = get_logger(__name__)

router = APIRouter(prefix="/review", tags=["review"])

# Singleton service
_service: ReviewService | None = None


def get_service() -> ReviewService:
    global _service
    if _service is None:
        _service = ReviewService()
    return _service


# =============================================================================
# ROUTES
# =============================================================================

@router.post("/analyze", response_model=ReviewResult)
async def analyze_artifact(request: ReviewRequest) -> ReviewResult:
    """
    Submit an artifact for AI review.
    
    Returns suggested patches that can be applied via /apply endpoint.
    
    Note: The gemini_api_key field is ephemeral and never persisted or logged.
    If not provided, the server-side configured key is used.
    """
    service = get_service()
    result = await service.review(request)
    
    if not result.success and result.error:
        logger.warning(f"Review failed: {result.error}")
    
    return result


@router.post("/apply", response_model=ApplyPatchesResult)
async def apply_patches(request: ApplyPatchesRequest) -> ApplyPatchesResult:
    """
    Apply approved patches to an artifact.
    
    Patches must come from a previous /analyze call on the same artifact.
    """
    service = get_service()
    result = await service.apply_patches(request)
    
    if not result.success and result.error:
        logger.warning(f"Apply patches failed: {result.error}")
    
    return result
