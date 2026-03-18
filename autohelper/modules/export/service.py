"""
Export service - CSV and other export formats.
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from autohelper.config import get_settings
from autohelper.shared.logging import get_logger

from .schemas import IntakeSubmissionData

logger = get_logger(__name__)


class ExportService:
    """Service for exporting data to various formats."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def export_intake_csv(
        self,
        form_id: str,
        form_title: str,
        submissions: list[IntakeSubmissionData],
        output_dir: str | None = None,
    ) -> tuple[str, int, list[str]]:
        """
        Export intake submissions to CSV.

        Args:
            form_id: The form ID for filename
            form_title: Human-readable form title for filename
            submissions: List of submission data
            output_dir: Output directory (defaults to exports/ in data dir)

        Returns:
            Tuple of (file_path, row_count, columns)
        """
        # Determine output directory
        # Default to exports/ subdirectory of data folder
        data_dir = Path(self.settings.db_path).parent
        base_exports_dir = data_dir / "exports"

        # Check configured export dir from settings
        configured_dir = getattr(self.settings, 'export_output_dir', '').strip()
        if not output_dir and configured_dir:
            # User-configured dir is trusted — use directly
            out_path = Path(configured_dir).resolve()
        elif output_dir:
            try:
                out_path = Path(output_dir).resolve()
                # API-provided paths must be within base_exports_dir for safety
                out_path.relative_to(base_exports_dir)
            except (ValueError, RuntimeError):
                logger.warning(
                    f"Invalid output_dir '{output_dir}'. Falling back to default exports directory."
                )
                out_path = base_exports_dir
        else:
            out_path = base_exports_dir

        out_path.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = self._sanitize_filename(form_title)
        filename = f"{safe_title}_{timestamp}.csv"
        file_path = out_path / filename

        # Collect all unique keys from metadata across all submissions
        all_keys: set[str] = set()
        for sub in submissions:
            all_keys.update(sub.metadata.keys())

        # Define columns: fixed fields + sorted metadata keys
        fixed_columns = ["id", "upload_code", "created_at"]
        metadata_columns = sorted(all_keys)
        all_columns = fixed_columns + metadata_columns

        # Write CSV
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=all_columns)
            writer.writeheader()

            for sub in submissions:
                row: dict[str, Any] = {
                    "id": sub.id,
                    "upload_code": sub.upload_code,
                    "created_at": sub.created_at,
                }
                # Add metadata fields
                for key in metadata_columns:
                    value = sub.metadata.get(key, "")
                    # Flatten nested structures to string
                    if isinstance(value, (dict, list)):
                        row[key] = str(value)
                    else:
                        row[key] = value

                writer.writerow(row)

        logger.info(f"Exported {len(submissions)} submissions to {file_path}")
        return str(file_path), len(submissions), all_columns

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize a string for use as filename."""
        # Replace spaces and special chars
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        # Limit length and strip
        safe = safe[:50].strip("_")

        # Ensure not empty
        if not safe:
            timestamp = datetime.now().strftime("%H%M%S")
            return f"export_{timestamp}"

        return safe
