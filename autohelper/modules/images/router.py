"""Image proxy — serves local images to the review engine frontend."""

import os
from pathlib import Path
from threading import Lock

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse

from autohelper.config import get_settings

from .report import generate_report

router = APIRouter(prefix="/api", tags=["images"])

MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".bmp": "image/bmp",
}

# Simple in-memory cache for best-resolution path lookups
_hires_cache: dict[str, Path] = {}
_hires_cache_lock = Lock()


def _get_image_dimensions(filepath: Path) -> tuple[int, int] | None:
    """Read image dimensions without loading full image into memory."""
    try:
        from PIL import Image
        with Image.open(filepath) as img:
            return img.size  # (width, height)
    except Exception:
        return None


def _resolve_image(path: str, allowed_roots: list[str]) -> Path | None:
    """Try to resolve an image path against allowed roots.

    Handles both absolute paths (validated against roots) and relative paths
    (tried as root/path for each root until a file is found).
    For relative paths found under multiple roots, returns highest resolution.
    """
    p = Path(path)

    if p.is_absolute():
        resolved = p.resolve()
        for root in allowed_roots:
            if str(resolved).lower().startswith(str(Path(root).resolve()).lower()):
                if resolved.is_file():
                    return resolved
        return None

    # Check cache first
    cache_key = path.lower()
    with _hires_cache_lock:
        if cache_key in _hires_cache:
            cached = _hires_cache[cache_key]
            if cached.is_file():
                return cached

    # Relative path — collect ALL valid matches across roots
    candidates: list[Path] = []
    for root in allowed_roots:
        candidate = (Path(root) / path).resolve()
        # Security: ensure resolved path is still under the root
        if str(candidate).lower().startswith(str(Path(root).resolve()).lower()):
            if candidate.is_file():
                candidates.append(candidate)

    if not candidates:
        return None

    if len(candidates) == 1:
        best = candidates[0]
    else:
        # Multiple matches — pick highest resolution
        best = candidates[0]
        best_pixels = 0
        for c in candidates:
            dims = _get_image_dimensions(c)
            if dims:
                pixels = dims[0] * dims[1]
                if pixels > best_pixels:
                    best_pixels = pixels
                    best = c
            elif best_pixels == 0:
                # Fallback: largest file size if PIL fails
                try:
                    size = os.path.getsize(c)
                    if size > best_pixels:
                        best_pixels = size
                        best = c
                except OSError:
                    pass

    with _hires_cache_lock:
        _hires_cache[cache_key] = best

    return best


@router.get("/image", include_in_schema=False)
async def serve_image(path: str = Query(..., description="Path to the image file")):
    """Serve a local image file, restricted to configured allowed roots."""
    settings = get_settings()

    allowed_roots = settings.image_allowed_roots
    if not allowed_roots:
        raise HTTPException(403, "No image roots configured — add directories in Submissions settings")

    resolved = _resolve_image(path, allowed_roots)
    if resolved is None:
        raise HTTPException(404, f"Image not found under any configured root")

    content_type = MIME_TYPES.get(resolved.suffix.lower(), "application/octet-stream")
    return FileResponse(
        str(resolved),
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/images/report")
async def image_report(manifest: str = Query(..., description="Manifest ID")):
    """Generate a JSON report of native image sizes for all records."""
    settings = get_settings()
    rows = generate_report(manifest, settings.image_allowed_roots)
    return rows


