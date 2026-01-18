"""
OneDrive file operations for pushing email attachments to project folders.
Uses local OneDrive sync folder (no API needed).

Features:
- Push attachments to project directory tree
- Prepend date code (YYYY-MM-DD_) to filename
- Check for duplicates before copying
"""

import os
import shutil
from datetime import datetime
from typing import Optional, List, Dict
from pathlib import Path

# Default OneDrive root - Public Art Projects
ONEDRIVE_ROOT = r"C:\Users\Neal\Ballard Fine Art\One Drive - BALLARD FINE ART - ALL FILES\1. PUBLIC ART\ALL PROJECTS"
UNSORTED_FOLDER = "_Unsorted"  # Fallback folder when project can't be identified

def get_onedrive_project_path(developer: str, project: str) -> Path:
    """
    Get the OneDrive path for a project's files.
    Structure: OneDrive/Developer - Project/
    """
    project_folder = f"{developer} - {project}"
    return Path(ONEDRIVE_ROOT) / project_folder


def format_date_prefix(date: Optional[datetime] = None) -> str:
    """Format date as YYYY-MM-DD_ prefix"""
    if date is None:
        date = datetime.now()
    return date.strftime("%Y-%m-%d_")


def file_already_exists(target_dir: Path, original_filename: str, date_prefix: str) -> Dict:
    """
    Check if a file with the same name (with or without date prefix) already exists.
    
    Returns:
        dict with:
        - exists: bool
        - existing_path: path to existing file if found
        - match_type: 'exact', 'dated', or None
    """
    dated_filename = f"{date_prefix}{original_filename}"
    
    # Check for exact match (already dated)
    dated_path = target_dir / dated_filename
    if dated_path.exists():
        return {"exists": True, "existing_path": str(dated_path), "match_type": "exact"}
    
    # Check if any file with same base name exists (with any date prefix)
    for existing_file in target_dir.glob(f"*_{original_filename}"):
        # Verify it's a date-prefixed version
        prefix = existing_file.name.replace(original_filename, "").rstrip("_")
        if len(prefix) == 10:  # YYYY-MM-DD
            try:
                datetime.strptime(prefix, "%Y-%m-%d")
                return {"exists": True, "existing_path": str(existing_file), "match_type": "dated"}
            except ValueError:
                pass
    
    # Also check for original filename without prefix
    original_path = target_dir / original_filename
    if original_path.exists():
        return {"exists": True, "existing_path": str(original_path), "match_type": "original"}
    
    return {"exists": False, "existing_path": None, "match_type": None}


def push_attachment_to_project(
    source_path: str,
    developer: str,
    project: str,
    subfolder: Optional[str] = None,
    email_date: Optional[datetime] = None,
    force: bool = False,
    use_ai_naming: bool = True
) -> Dict:
    """
    Push an attachment file to the project's OneDrive folder.
    
    Args:
        source_path: Path to the attachment file
        developer: Developer name (e.g., "Qualex")
        project: Project name (e.g., "Artesia")
        subfolder: Optional subfolder within project (e.g., "Contracts", "Reports")
        email_date: Date to use for prefix (defaults to now)
        force: If True, overwrite existing files
        use_ai_naming: If True, clean up filename using AI
    
    Returns:
        dict with success status and details
    """
    source = Path(source_path)
    
    if not source.exists():
        return {"success": False, "error": f"Source file not found: {source_path}"}
    
    # Build target directory
    target_dir = get_onedrive_project_path(developer, project)
    if subfolder:
        target_dir = target_dir / subfolder
    
    # Create directory if needed
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Get original filename and optionally clean it up with AI
    original_filename = source.name
    if use_ai_naming:
        try:
            from .ai_naming import generate_legible_filename
            clean_filename = generate_legible_filename(original_filename, context=f"{developer} {project}")
        except Exception:
            clean_filename = original_filename
    else:
        clean_filename = original_filename
    
    # Generate dated filename
    date_prefix = format_date_prefix(email_date)
    dated_filename = f"{date_prefix}{clean_filename}"
    target_path = target_dir / dated_filename
    
    # Check for duplicates (check both original and cleaned names)
    if not force:
        check = file_already_exists(target_dir, clean_filename, date_prefix)
        if check["exists"]:
            return {
                "success": False,
                "error": "File already exists",
                "existing_path": check["existing_path"],
                "match_type": check["match_type"],
                "skipped": True
            }
    
    # Copy file
    try:
        shutil.copy2(source, target_path)
        return {
            "success": True,
            "source": str(source),
            "target": str(target_path),
            "filename": dated_filename,
            "original_filename": original_filename,
            "renamed": original_filename != clean_filename
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def push_multiple_attachments(
    attachments: List[Dict],
    developer: str,
    project: str,
    email_date: Optional[datetime] = None
) -> Dict:
    """
    Push multiple attachments to a project folder.
    
    Args:
        attachments: List of {"path": str, "subfolder": Optional[str]}
        developer: Developer name
        project: Project name
        email_date: Date to use for prefix
    
    Returns:
        dict with summary of results
    """
    results = {
        "success": [],
        "skipped": [],
        "errors": []
    }
    
    for attachment in attachments:
        result = push_attachment_to_project(
            source_path=attachment["path"],
            developer=developer,
            project=project,
            subfolder=attachment.get("subfolder"),
            email_date=email_date
        )
        
        if result.get("success"):
            results["success"].append({
                "filename": result["filename"],
                "target": result["target"]
            })
        elif result.get("skipped"):
            results["skipped"].append({
                "filename": Path(attachment["path"]).name,
                "existing": result["existing_path"]
            })
        else:
            results["errors"].append({
                "filename": Path(attachment["path"]).name,
                "error": result["error"]
            })
    
    return {
        "total": len(attachments),
        "pushed": len(results["success"]),
        "skipped": len(results["skipped"]),
        "errors": len(results["errors"]),
        "details": results
    }


def get_project_folders() -> List[str]:
    """List all project folders in OneDrive"""
    root_path = Path(ONEDRIVE_ROOT)
    
    if not root_path.exists():
        return []
    
    return [f.name for f in root_path.iterdir() if f.is_dir()]


def find_project_folder(search_term: str) -> Optional[str]:
    """Find a project folder by partial name match"""
    folders = get_project_folders()
    search_lower = search_term.lower()
    
    matches = [f for f in folders if search_lower in f.lower()]
    
    if len(matches) == 1:
        return matches[0]
    
    return None


def resolve_project_folder(
    developer: Optional[str] = None,
    project: Optional[str] = None,
    monday_board_name: Optional[str] = None,
    create_if_missing: bool = True
) -> Dict:
    """
    Resolve the correct project folder using cross-referencing logic.
    
    Priority:
    1. Exact match: Developer - Project
    2. Monday board name match
    3. Fuzzy search on project name (single match only)
    4. Auto-create if Monday board found but no folder
    5. Fallback to _Unsorted
    
    Returns:
        dict with:
        - path: Path to the resolved folder
        - folder_name: Name of the folder
        - method: How the folder was resolved ('exact', 'monday', 'fuzzy', 'created', 'unsorted')
        - created: bool if folder was newly created
    """
    root = Path(ONEDRIVE_ROOT)
    folders = get_project_folders()
    
    # 1. Try exact Developer - Project match
    if developer and project:
        exact_name = f"{developer} - {project}"
        if exact_name in folders:
            return {
                "path": str(root / exact_name),
                "folder_name": exact_name,
                "method": "exact",
                "created": False
            }
    
    # 2. Try Monday board name match
    if monday_board_name:
        # Monday boards are like "Developer - Project - Type", strip the Type part
        parts = monday_board_name.split(" - ")
        if len(parts) >= 2:
            monday_folder_name = f"{parts[0]} - {parts[1]}"
            if monday_folder_name in folders:
                return {
                    "path": str(root / monday_folder_name),
                    "folder_name": monday_folder_name,
                    "method": "monday",
                    "created": False
                }
            
            # 3. Auto-create if Monday board found but folder doesn't exist
            if create_if_missing:
                new_folder = root / monday_folder_name
                new_folder.mkdir(parents=True, exist_ok=True)
                return {
                    "path": str(new_folder),
                    "folder_name": monday_folder_name,
                    "method": "created",
                    "created": True
                }
    
    # 4. Fuzzy search on project name
    if project:
        match = find_project_folder(project)
        if match:
            return {
                "path": str(root / match),
                "folder_name": match,
                "method": "fuzzy",
                "created": False
            }
    
    # 5. Fallback to Unsorted
    unsorted_path = root / UNSORTED_FOLDER
    unsorted_path.mkdir(parents=True, exist_ok=True)
    return {
        "path": str(unsorted_path),
        "folder_name": UNSORTED_FOLDER,
        "method": "unsorted",
        "created": False
    }


# Test
if __name__ == "__main__":
    print(f"OneDrive root: {ONEDRIVE_ROOT}")
    
    # Check if path exists
    if Path(ONEDRIVE_ROOT).exists():
        print("✓ OneDrive folder found")
        
        folders = get_project_folders()
        print(f"\nFound {len(folders)} project folders:")
        for f in folders[:10]:
            print(f"  - {f}")
        
        # Test resolve_project_folder
        print("\nTesting resolve_project_folder:")
        result = resolve_project_folder(project="Artesia")
        print(f"  project='Artesia' -> {result['folder_name']} ({result['method']})")
    else:
        print("✗ OneDrive folder not found")

