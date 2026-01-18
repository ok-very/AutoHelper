"""
Generate service implementation.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from autohelper.infra.fs.local_fs import local_fs
from autohelper.modules.reference.schemas import ReferenceCreate
from autohelper.modules.reference.service import ReferenceService
from autohelper.shared.logging import get_logger
from autohelper.shared.time import utcnow_iso

from .schemas import ArtifactResponse, IntakeManifestRequest, ReportRequest

logger = get_logger(__name__)


class GenerateService:
    """Service for generating filesystem artifacts."""

    def __init__(self) -> None:
        self.ref_service = ReferenceService()

    def _safe_write(self, path: Path, content: str | bytes, overwrite: bool = False) -> Path:
        """
        Atomic write to file.
        Writes to a temp file in the same directory, then renames.
        """
        if path.exists() and not overwrite:
            raise FileExistsError(f"File already exists: {path}")

        # Ensure parent exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write to temp file in same directory to ensure atomic rename (same filesystem)
        prefix = f".tmp_{path.name}_"
        is_text = isinstance(content, str)
        
        fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=prefix, text=is_text)
        
        try:
            with os.fdopen(fd, 'w' if is_text else 'wb') as f:
                f.write(content)
            
            # Atomic rename (replace allows overwrite if it appeared in race, 
            # but we checked existence above. Windows needs replace for overwrite.)
            os.replace(tmp_path, path)
            
        except Exception as e:
            # Cleanup temp file on error
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise e
            
        return path

    def generate_intake_manifest(self, req: IntakeManifestRequest) -> ArtifactResponse:
        """
        Generate an intake manifest JSON file listing files in the folder.
        """
        folder_path = Path(req.intake_folder).resolve()
        
        if not local_fs.is_dir(folder_path):
             raise ValueError(f"Intake folder not found or not a directory: {folder_path}")

        # Enumerate files
        files_data = []
        # Walk locally
        for p, _, files in local_fs.walk(folder_path):
            for filename in sorted(files):
                file_path = p / filename
                
                # Skip the manifest itself and hidden files
                if file_path.name == "_intake_manifest.json" or file_path.name.startswith('.'):
                    continue
                    
                st = local_fs.stat(file_path)
                
                # Calculate relative path
                try:
                    rel_path = str(file_path.relative_to(folder_path)).replace('\\', '/')
                except ValueError:
                    rel_path = file_path.name

                files_data.append({
                    "path": rel_path,
                    "size": st.size,
                    "mtime_ns": st.mtime_ns,
                    "is_file": True
                })

        # Build content
        manifest_content = {
            "context_id": req.context_id,
            "generated_at": utcnow_iso(),
            "intake_folder": str(folder_path),
            "file_count": len(files_data),
            "files": files_data
        }
        
        json_content = json.dumps(manifest_content, indent=2, sort_keys=True)
        
        # Output path
        manifest_path = folder_path / "_intake_manifest.json"
        
        # Check overwrite option
        overwrite = req.options.get("overwrite", False) if req.options else False
        
        self._safe_write(manifest_path, json_content, overwrite=overwrite)
        
        # Register artifact
        ref = self.ref_service.register(ReferenceCreate(
            path=str(manifest_path),
            context_id=req.context_id,
            work_item_id=req.context_id, # Linking context as work item for traceability
            note="Generated intake manifest"
        ))
        
        return ArtifactResponse(
            ref_id=ref.ref_id,
            path=ref.path,
            artifact_type="intake_manifest"
        )

    def generate_report(self, req: ReportRequest) -> ArtifactResponse:
        """
        Generate a report markdown file from payload.
        """
        # For Minimum Viable Product, we treat 'template' as the raw markdown format string
        # or we could implement basic named templates.
        # User plan says: "Validate template identifier... Render markdown"
        
        # Simple rendering for now: Replace {{key}} in template string
        content = req.template
        for key, value in req.payload.items():
            content = content.replace(f"{{{{{key}}}}}", str(value))
            
        # Determine output path
        # If options specify 'folder', use it. Otherwise use a default location?
        # The user plan says: "Write _report.md... expected project folder"
        # We need a path hint in options or derive from context.
        # Let's require 'output_folder' in options for now, or fail.
        
        output_folder_str = req.options.get("output_folder") if req.options else None
        if not output_folder_str:
             # Fallback: try to write to a 'Reports' folder in current working dir? 
             # Or error. Error is safer.
             raise ValueError("Option 'output_folder' is required for report generation")
             
        output_folder = Path(output_folder_str).resolve()
        if not output_folder.exists():
             output_folder.mkdir(parents=True, exist_ok=True)
             
        filename = f"_report_{req.context_id}.md"
        report_path = output_folder / filename
        
        overwrite = req.options.get("overwrite", False) if req.options else False
        
        self._safe_write(report_path, content, overwrite=overwrite)
        
        # Register
        ref = self.ref_service.register(ReferenceCreate(
            path=str(report_path),
            context_id=req.context_id,
            work_item_id=req.context_id,
            note="Generated report artifact"
        ))
        
        return ArtifactResponse(
            ref_id=ref.ref_id,
            path=ref.path,
            artifact_type="report"
        )
