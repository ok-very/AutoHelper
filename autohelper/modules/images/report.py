"""Report generation — native image dimensions for all records in a manifest."""

import csv
import io
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

MANIFESTS_DIR = Path(__file__).resolve().parent.parent.parent / "gui" / "manifests"


def _get_dimensions(filepath: Path) -> tuple[int, int] | None:
    try:
        from PIL import Image
        with Image.open(filepath) as img:
            return img.size
    except Exception:
        return None


def _resolve_best(rel_path: str, roots: list[str]) -> Path | None:
    """Find the highest-resolution copy of a relative image path across roots."""
    candidates: list[Path] = []
    for root in roots:
        candidate = (Path(root) / rel_path).resolve()
        if str(candidate).lower().startswith(str(Path(root).resolve()).lower()):
            if candidate.is_file():
                candidates.append(candidate)

    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    best = candidates[0]
    best_pixels = 0
    for c in candidates:
        dims = _get_dimensions(c)
        if dims:
            pixels = dims[0] * dims[1]
            if pixels > best_pixels:
                best_pixels = pixels
                best = c
        elif best_pixels == 0:
            try:
                size = os.path.getsize(c)
                if size > best_pixels:
                    best_pixels = size
                    best = c
            except OSError:
                pass
    return best


def generate_report(
    manifest_id: str,
    image_allowed_roots: list[str],
    review_states: dict | None = None,
) -> list[dict]:
    """Load manifest + records, resolve images, return dimension data with review selections."""
    manifest_path = MANIFESTS_DIR / f"{manifest_id}.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest not found: {manifest_id}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    records_rel = manifest.get("dataSources", {}).get("records", "")
    records_rel = records_rel.lstrip("/")
    if records_rel.startswith("manifests/"):
        records_rel = records_rel[len("manifests/"):]
    records_path = MANIFESTS_DIR / records_rel

    if not records_path.is_file():
        raise FileNotFoundError(f"Records file not found: {records_path}")

    records = json.loads(records_path.read_text(encoding="utf-8"))

    # Build tier lookup from manifest
    tiers = {}
    for tier in manifest.get("imagePipeline", {}).get("metricTiers", []):
        tiers[tier["id"]] = tier

    # Use manifest imageBases if available, fall back to config roots
    roots = manifest.get("dataSources", {}).get("imageBases", image_allowed_roots)

    # Index review states by record ID
    rs_map = review_states or {}

    # Determine the record ID field
    record_id_field = manifest.get("recordId", "id")

    rows: list[dict] = []
    for rec in records:
        rec_id = str(rec.get(record_id_field, ""))
        rs = rs_map.get(rec_id, {})

        image_path = rec.get("image_path", "")

        # Review state data
        selected_dpi_ids = rs.get("selectedDpis", []) or []
        assignments = rs.get("assignments", {})
        confirmed = rs.get("confirmed", False)
        rank = rs.get("rank", 0)

        # Resolve selected DPI labels
        selected_labels = []
        for sid in selected_dpi_ids:
            if sid in tiers:
                selected_labels.append(tiers[sid].get("label", sid))


        w, h, fsize = None, None, None
        if image_path:
            resolved = _resolve_best(image_path, roots)
            if resolved:
                dims = _get_dimensions(resolved)
                if dims:
                    w, h = dims
                try:
                    fsize = os.path.getsize(resolved)
                except OSError:
                    pass

        row = {
            "artist_name": rec.get("artist_name", ""),
            "title": rec.get("title", ""),
            "location_text": rec.get("location_text", ""),
            "image_path": image_path,
            "width_px": w,
            "height_px": h,
            "file_bytes": fsize,
            "floor": assignments.get("floor", []),
            "category": assignments.get("category", []),
            "confirmed": confirmed,
            "rank": rank,
            "selected_dpis": " | ".join(selected_labels),
        }

        # Print sizes at all DPI tiers
        for tier_id, tier in tiers.items():
            dpi = tier.get("dpi", 300)
            scale = tier.get("scale", 1)
            if w and h:
                row[f"print_w_{tier_id}"] = round((w * scale) / dpi, 2)
                row[f"print_h_{tier_id}"] = round((h * scale) / dpi, 2)
            else:
                row[f"print_w_{tier_id}"] = None
                row[f"print_h_{tier_id}"] = None

        rows.append(row)

    return rows


def report_to_csv(rows: list[dict]) -> str:
    """Convert report rows to CSV string."""
    if not rows:
        return ""

    # Build fieldnames from first row to capture dynamic tier columns
    base_fields = [
        "artist_name", "title", "location_text", "image_path",
        "width_px", "height_px", "file_bytes",
        "floor", "category", "confirmed", "rank",
        "selected_dpis",
    ]
    # Add any print_w_*/print_h_* columns from the first row
    extra = sorted(k for k in rows[0] if k.startswith("print_") and k not in base_fields)
    fieldnames = base_fields + extra

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()
