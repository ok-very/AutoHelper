"""
Filetree module schemas.
"""

from pydantic import BaseModel


class FiletreeRequest(BaseModel):
    """Request parameters for filetree endpoint."""

    root_id: str | None = None  # Filter to specific root
    max_depth: int = 10  # Limit tree depth
    extensions: list[str] | None = None  # Filter by extension (e.g., [".pdf", ".txt"])


class FiletreeNode(BaseModel):
    """A node in the filetree hierarchy."""

    name: str  # Filename or directory name
    path: str  # Relative path from root
    is_dir: bool
    children: list["FiletreeNode"] | None = None  # None for files, list for dirs
    size: int | None = None  # File size in bytes (None for dirs)
    ext: str | None = None  # File extension (None for dirs)


class FiletreeResponse(BaseModel):
    """Response from filetree endpoint."""

    roots: list[FiletreeNode]  # Top-level roots as tree nodes
