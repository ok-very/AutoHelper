"""
Search module schemas.
"""

from typing import Any
from pydantic import BaseModel


class FileResult(BaseModel):
    """File result in search response."""
    file_id: str
    path: str
    root_id: str
    size: int
    mtime: int
    is_dir: bool = False
    
    class Config:
        from_attributes = True


class SearchResponse(BaseModel):
    """Response for search query."""
    items: list[FileResult]
    total: int
    took_ms: int
