"""
Reference module schemas.
"""

from typing import Any
from datetime import datetime
from pydantic import BaseModel, Field


class ReferenceCreate(BaseModel):
    """Request to create/update a reference."""
    path: str
    work_item_id: str | None = None
    context_id: str | None = None
    note: str | None = None


class ReferenceDTO(BaseModel):
    """Reference data object."""
    ref_id: str
    file_id: str | None
    path: str
    status: str  # active, broken, resolved
    created_at: datetime
    
    class Config:
        from_attributes = True


class ResolveRequest(BaseModel):
    """Request to resolve a reference."""
    ref_id: str


class ResolutionResult(BaseModel):
    """Result of resolution attempt."""
    ref_id: str
    found: bool
    path: str | None
    confidence: float # 1.0 = exact match, < 1.0 = fuzzy/hash match
    strategy: str # 'exact', 'hash', 'heuristic'
    file_info: dict[str, Any] | None = None
