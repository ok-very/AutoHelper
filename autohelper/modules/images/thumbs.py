"""Thumbnail generation for report images."""

import hashlib
import logging
import math
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)

MANIFESTS_DIR = Path(__file__).resolve().parent.parent.parent / "gui" / "manifests"


def generate_thumbnail(
    source: Path,
    dest: Path,
    max_area_px: int = 15000,
    quality: int = 80,
) -> bool:
    """Resize source image so width*height <= max_area_px, save as JPEG."""
    try:
        with Image.open(source) as img:
            w, h = img.size
            area = w * h
            if area > max_area_px and area > 0:
                scale = math.sqrt(max_area_px / area)
                new_w = max(1, round(w * scale))
                new_h = max(1, round(h * scale))
                img = img.resize((new_w, new_h), Image.LANCZOS)

            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            dest.parent.mkdir(parents=True, exist_ok=True)
            img.save(dest, "JPEG", quality=quality, optimize=True)
            return True
    except Exception:
        logger.warning("Failed to generate thumbnail for %s", source, exc_info=True)
        return False


def _resolve_best(rel_path: str, roots: list[str]) -> Path | None:
    """Find an image file across roots."""
    for root in roots:
        candidate = (Path(root) / rel_path).resolve()
        if str(candidate).lower().startswith(str(Path(root).resolve()).lower()):
            if candidate.is_file():
                return candidate
    return None


def ensure_thumbnails(
    manifest_id: str,
    records: list[dict],
    roots: list[str],
    max_area_px: int = 15000,
    quality: int = 80,
) -> dict[str, str]:
    """Generate thumbnails for all records, return {image_path: thumb_relative_url}.

    Thumbnails are stored in gui/manifests/{manifest_id}/thumbs/ and served
    via the existing /manifests static mount.
    """
    thumbs_dir = MANIFESTS_DIR / manifest_id / "thumbs"
    result: dict[str, str] = {}

    for rec in records:
        image_path = rec.get("image_path", "")
        if not image_path:
            continue

        # Deterministic filename from path
        path_hash = hashlib.md5(image_path.encode()).hexdigest()
        thumb_name = f"{path_hash}.jpg"
        thumb_path = thumbs_dir / thumb_name

        # Skip if thumb exists and is newer than source
        source = _resolve_best(image_path, roots)
        if source is None:
            continue

        if thumb_path.is_file():
            try:
                if thumb_path.stat().st_mtime >= source.stat().st_mtime:
                    result[image_path] = f"/manifests/{manifest_id}/thumbs/{thumb_name}"
                    continue
            except OSError:
                pass

        if generate_thumbnail(source, thumb_path, max_area_px, quality):
            result[image_path] = f"/manifests/{manifest_id}/thumbs/{thumb_name}"

    return result
