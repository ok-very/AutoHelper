"""
Filesystem walker: discovers artist folders and builds raw inventory records.

Generalized from BFA-artist-lists to handle four layout types:
  - nation_based: <Nation>/<ArtistFolder>/
  - bucketed:     <LetterBucket>/<ArtistFolder>/  (e.g. "Artists A-D")
  - flat:         <ArtistFolder>/

Produces a list of FolderRecord dicts, one per physical artist folder.
The resolver merges duplicates.
"""
from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .config import (
    CATEGORY_PRIORITY,
    CategoryProfile,
    get_lexicon,
    is_artist_folder,
)
from .utils import (
    classify_file,
    generate_artist_id,
    is_current_tearsheet,
    normalise_subfolder,
    parse_concept_proposal_file,
    parse_concept_proposal_folder,
    parse_date_from_filename,
    parse_display_name,
    parse_eoi_folder,
    read_url_file,
)

logger = logging.getLogger(__name__)


class ArtistScanner:
    """Discovers and scans artist folders from a storage root."""

    def __init__(
        self,
        storage_root: Path,
        categories: list[CategoryProfile] | None = None,
    ):
        self.storage_root = storage_root
        lex = get_lexicon()
        self.categories = categories or lex.categories

    def scan_all(
        self,
        progress_cb: Callable[[str], None] | None = None,
        cancel: threading.Event | None = None,
    ) -> list[dict[str, Any]]:
        """Scan all categories under the storage root. Returns raw folder records."""
        records: list[dict[str, Any]] = []
        emit = progress_cb or (lambda _msg: None)

        for cat in self.categories:
            if cancel and cancel.is_set():
                break

            cat_path = self.storage_root / cat.rel_path
            if not cat_path.is_dir():
                logger.debug("Category path not found, skipping: %s", cat_path)
                continue

            emit(f"Scanning category: {cat.label}")

            if cat.layout == "nation_based":
                records.extend(self._scan_nation_based(cat_path, cat.key, emit, cancel))
            elif cat.layout == "bucketed":
                records.extend(self._scan_bucketed(cat_path, cat.key, emit, cancel))
            elif cat.layout == "flat":
                records.extend(self._scan_flat(cat_path, cat.key, emit, cancel))
            else:
                logger.warning("Unknown layout '%s' for category '%s'", cat.layout, cat.key)

            emit(f"  {cat.label}: {len(records)} folders so far")

        emit(f"Folder walk complete: {len(records)} records")
        return records

    def scan_single_folder(
        self,
        folder_path: Path,
        category: str,
        nation: str | None = None,
    ) -> dict[str, Any]:
        """Re-scan a single artist folder. Used for watchdog-triggered updates."""
        folder_name = folder_path.name
        return scan_artist_folder(
            category=category,
            nation=nation,
            folder_name=folder_name,
            folder_path=str(folder_path),
        )

    # ------------------------------------------------------------------
    # Layout handlers
    # ------------------------------------------------------------------

    def _scan_nation_based(
        self, cat_path: Path, category: str,
        emit: Callable[[str], None] = lambda _: None,
        cancel: threading.Event | None = None,
    ) -> list[dict]:
        """Walk <Nation>/<ArtistFolder>/ structure."""
        lex = get_lexicon()
        records = []
        try:
            nations = sorted(os.listdir(cat_path))
        except PermissionError:
            return records

        for nation in nations:
            if cancel and cancel.is_set():
                break
            nation_path = os.path.join(cat_path, nation)
            if not os.path.isdir(nation_path):
                continue
            if nation.lower() in lex.ignore_dirs:
                continue

            emit(f"  {category}/{nation}")

            try:
                artist_folders = sorted(os.listdir(nation_path))
            except PermissionError:
                continue

            for artist_folder in artist_folders:
                artist_path = os.path.join(nation_path, artist_folder)
                if not os.path.isdir(artist_path) or artist_folder.lower() in lex.ignore_dirs:
                    continue
                if not is_artist_folder(artist_folder):
                    continue

                record = scan_artist_folder(
                    category=category,
                    nation=nation,
                    folder_name=artist_folder,
                    folder_path=artist_path,
                )
                records.append(record)

        return records

    def _scan_bucketed(
        self, cat_path: Path, category: str,
        emit: Callable[[str], None] = lambda _: None,
        cancel: threading.Event | None = None,
    ) -> list[dict]:
        """Walk <LetterBucket>/<ArtistFolder>/ structure (e.g. PRIVATE ART)."""
        lex = get_lexicon()
        records = []
        try:
            buckets = sorted(os.listdir(cat_path))
        except PermissionError:
            return records

        for bucket in buckets:
            if cancel and cancel.is_set():
                break
            if bucket.startswith("z_") or bucket.lower() in lex.ignore_dirs:
                continue
            bucket_path = os.path.join(cat_path, bucket)
            if not os.path.isdir(bucket_path):
                continue

            emit(f"  {category}/{bucket}")

            try:
                artist_folders = sorted(os.listdir(bucket_path))
            except PermissionError:
                continue

            for artist_folder in artist_folders:
                if artist_folder.startswith("a ") or artist_folder.startswith("z_"):
                    continue
                artist_path = os.path.join(bucket_path, artist_folder)
                if not os.path.isdir(artist_path):
                    continue
                if not is_artist_folder(artist_folder):
                    continue

                record = scan_artist_folder(
                    category=category,
                    nation=None,
                    folder_name=artist_folder,
                    folder_path=artist_path,
                )
                records.append(record)

        return records

    def _scan_flat(
        self, cat_path: Path, category: str,
        emit: Callable[[str], None] = lambda _: None,
        cancel: threading.Event | None = None,
    ) -> list[dict]:
        """Walk flat <ArtistFolder>/ structure (e.g. CORPORATE ART)."""
        lex = get_lexicon()
        records = []
        try:
            artist_folders = sorted(os.listdir(cat_path))
        except PermissionError:
            return records

        for artist_folder in artist_folders:
            if cancel and cancel.is_set():
                break
            if artist_folder.lower() in lex.ignore_dirs or artist_folder.startswith("z_"):
                continue
            artist_path = os.path.join(cat_path, artist_folder)
            if not os.path.isdir(artist_path):
                continue
            if not is_artist_folder(artist_folder):
                continue

            record = scan_artist_folder(
                category=category,
                nation=None,
                folder_name=artist_folder,
                folder_path=artist_path,
            )
            records.append(record)

        return records


# ======================================================================
# Folder-level scanning
# ======================================================================

def scan_artist_folder(
    category: str,
    nation: str | None,
    folder_name: str,
    folder_path: str,
) -> dict[str, Any]:
    """Scan a single artist folder and return a FolderRecord dict."""
    lex = get_lexicon()

    fixed_name = lex.folder_name_fixes.get(folder_name, folder_name)
    artist_id = generate_artist_id(fixed_name)
    display_name, first_name, last_name = parse_display_name(fixed_name)

    # Check for collaborative entity
    collab_key = f"{category}:{nation or ''}:{folder_name}"
    collab_cfg = lex.collaborative_entities.get(collab_key)
    is_collaborative = collab_cfg is not None

    # Check for nested artist structure
    nested_key = f"{category}:{nation or ''}:{folder_name}"
    nested_cfg = lex.nested_artists.get(nested_key)
    if nested_cfg:
        display_name = (
            f"{nested_cfg['traditional_name']} "
            f"({nested_cfg['western_first']} {nested_cfg['western_last']})"
        )
        first_name = nested_cfg["western_first"]
        last_name = nested_cfg["western_last"]

    # --- Identity hints ---
    # Collect identity-relevant data discoverable from the filesystem.
    # Identities like "queer", "PoC", etc. are editorial — they come from the
    # dashboard UI, AI enrichment, or lexicon overrides.  The scanner's job
    # is to capture what's structurally available (nation, existing manifest
    # identity data) so it survives rescans.
    identity_hints: dict[str, Any] = {
        "identities": [],
        "affiliations": [],   # list of {"name": ..., "type": ...}
        "locations": [],      # list of {"place": ..., "type": ...}
    }
    if nation:
        identity_hints["affiliations"].append({"name": nation, "type": "nation"})

    # Check for per-artist identity overrides in the lexicon
    artist_identity_key = f"{category}:{nation or ''}:{folder_name}"
    artist_identity_cfg = lex.artist_identity_overrides.get(artist_identity_key, {})
    if artist_identity_cfg:
        identity_hints["identities"].extend(artist_identity_cfg.get("identities", []))
        for aff in artist_identity_cfg.get("affiliations", []):
            identity_hints["affiliations"].append(aff)
        for loc in artist_identity_cfg.get("locations", []):
            identity_hints["locations"].append(loc)
        if artist_identity_cfg.get("pronouns"):
            identity_hints["pronouns"] = artist_identity_cfg["pronouns"]
        if artist_identity_cfg.get("career_stage"):
            identity_hints["career_stage"] = artist_identity_cfg["career_stage"]

    # Recover identity tags from an existing on-disk manifest (so editorial
    # tags set via the dashboard or AI enrichment are not lost on rescan)
    _recover_identity_from_manifest(identity_hints, folder_path)

    record: dict[str, Any] = {
        "artist_id": artist_id,
        "category": category,
        "nation": nation,
        "folder_name": folder_name,
        "folder_name_fixed": fixed_name,
        "folder_path": folder_path,
        "display_name": display_name,
        "first_name": first_name,
        "last_name": last_name,
        "is_collaborative": is_collaborative,
        "collab_cfg": collab_cfg,
        "nested_cfg": nested_cfg,
        "identity_hints": identity_hints,
        "bios": [],
        "cvs": [],
        "tearsheets": [],
        "project_lists": [],
        "eois": [],
        "concept_proposals": [],
        "image_paths": [],
        "image_count": 0,
        "website_urls": [],
        "loose_docs": [],
        "review_notes": [],
    }

    # Walk the artist folder
    _walk_artist_dir(record, folder_path, folder_path, nested_cfg)

    record["image_count"] = len(record["image_paths"])

    # Resolve canonical_id via multi-folder lookup
    lookup_key = (category, nation or "", folder_name)
    record["canonical_id"] = lex.multi_folder_lookup.get(lookup_key, artist_id)

    return record


def _walk_artist_dir(
    record: dict[str, Any],
    base_path: str,
    current_path: str,
    nested_cfg: dict | None,
    _depth: int = 0,
) -> None:
    """Recursively walk a directory and populate record fields."""
    lex = get_lexicon()

    try:
        entries = sorted(os.listdir(current_path))
    except PermissionError:
        return

    for entry in entries:
        entry_lower = entry.lower()
        entry_path = os.path.join(current_path, entry)

        if entry_lower in lex.ignore_files or entry_lower.startswith("."):
            continue

        if os.path.isdir(entry_path):
            if entry_lower in lex.ignore_dirs:
                continue

            canonical_sub = normalise_subfolder(entry)

            # Nested western-name subfolder
            if (
                nested_cfg
                and entry == nested_cfg.get("western_subfolder")
                and _depth == 0
            ):
                _walk_artist_dir(record, base_path, entry_path, None, _depth + 1)
                continue

            # Known subfolder types
            if canonical_sub == "Bio":
                _collect_docs(record, "bios", entry_path)
            elif canonical_sub == "CV":
                _collect_docs(record, "cvs", entry_path)
            elif canonical_sub == "Tearsheets":
                _collect_tearsheets(record, entry_path)
            elif canonical_sub == "Images":
                _collect_images(record, entry_path)
            elif canonical_sub == "Project list":
                _collect_docs(record, "project_lists", entry_path)
            elif canonical_sub == "EOI":
                _collect_eois(record, entry_path)
            elif canonical_sub == "Concept Proposals":
                _collect_concept_proposals(record, entry_path)
            else:
                # Unknown subfolder — recurse shallowly
                if _depth < 3:
                    _walk_artist_dir(record, base_path, entry_path, None, _depth + 1)

        else:
            # Files at current level
            ftype = classify_file(entry)

            if ftype == "ignore":
                continue
            elif ftype == "image":
                record["image_paths"].append(entry_path)
            elif ftype == "url":
                url = read_url_file(entry_path)
                if url:
                    record["website_urls"].append(url)
            elif ftype == "bio":
                record["bios"].append({
                    "file_path": entry_path,
                    "date": parse_date_from_filename(entry),
                    "is_current": True,
                })
            elif ftype == "cv":
                record["cvs"].append({
                    "file_path": entry_path,
                    "date": parse_date_from_filename(entry),
                    "is_current": True,
                })
            elif ftype == "tearsheet":
                record["tearsheets"].append({
                    "file_path": entry_path,
                    "date": parse_date_from_filename(entry),
                    "is_current": True,
                })
            elif ftype == "project_list":
                record["project_lists"].append({
                    "file_path": entry_path,
                    "date": parse_date_from_filename(entry),
                    "is_current": True,
                })
            elif ftype == "document":
                record["loose_docs"].append(entry_path)


# ======================================================================
# Collection helpers
# ======================================================================

def _collect_docs(record: dict, key: str, folder_path: str) -> None:
    """Collect document files from a Bio/CV/Project list folder."""
    lex = get_lexicon()
    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [d for d in dirs if d.lower() not in lex.ignore_dirs]
        for f in sorted(files):
            if f.lower() in lex.ignore_files or f.startswith("."):
                continue
            fpath = os.path.join(root, f)
            ftype = classify_file(f)
            if ftype in ("document", "bio", "cv", "project_list", "image", "other"):
                record[key].append({
                    "file_path": fpath,
                    "date": parse_date_from_filename(f),
                    "is_current": True,
                })


def _collect_tearsheets(record: dict, tearsheet_root: str) -> None:
    """Collect tearsheets, marking Old subfolder items as not current."""
    lex = get_lexicon()
    for root, dirs, files in os.walk(tearsheet_root):
        dirs[:] = [d for d in dirs if d.lower() not in lex.ignore_dirs]
        for f in sorted(files):
            if f.lower() in lex.ignore_files or f.startswith("."):
                continue
            fpath = os.path.join(root, f)
            ext = os.path.splitext(f.lower())[1]
            if ext in lex.image_extensions:
                continue
            current = is_current_tearsheet(fpath, tearsheet_root)
            record["tearsheets"].append({
                "file_path": fpath,
                "date": parse_date_from_filename(f),
                "is_current": current,
            })


def _collect_images(record: dict, images_root: str) -> None:
    """Recursively collect all image files."""
    lex = get_lexicon()
    for root, dirs, files in os.walk(images_root):
        dirs[:] = [d for d in dirs if d.lower() not in lex.ignore_dirs]
        for f in sorted(files):
            if f.lower() in lex.ignore_files or f.startswith("."):
                continue
            ext = os.path.splitext(f.lower())[1]
            if ext in lex.image_extensions:
                record["image_paths"].append(os.path.join(root, f))


def _collect_eois(record: dict, eoi_root: str) -> None:
    """Collect EOI entries — each subfolder is a project."""
    lex = get_lexicon()
    try:
        entries = sorted(os.listdir(eoi_root))
    except PermissionError:
        return

    for entry in entries:
        entry_path = os.path.join(eoi_root, entry)
        if entry.lower() in lex.ignore_files or entry.startswith("."):
            continue

        if os.path.isdir(entry_path):
            project_name = parse_eoi_folder(entry)
            primary_file = _find_primary_doc(entry_path)
            record["eois"].append({
                "project_name": project_name,
                "folder_path": entry_path,
                "file_path": primary_file,
            })
        else:
            ftype = classify_file(entry)
            if ftype != "ignore":
                project_name = parse_eoi_folder(os.path.splitext(entry)[0])
                record["eois"].append({
                    "project_name": project_name,
                    "folder_path": None,
                    "file_path": entry_path,
                })


def _collect_concept_proposals(record: dict, proposals_root: str) -> None:
    """Collect concept proposal entries — subfolders and loose files."""
    lex = get_lexicon()
    try:
        entries = sorted(os.listdir(proposals_root))
    except PermissionError:
        return

    for entry in entries:
        entry_path = os.path.join(proposals_root, entry)
        if entry.lower() in lex.ignore_files or entry.startswith("."):
            continue

        if os.path.isdir(entry_path):
            parsed = parse_concept_proposal_folder(entry)
            record["concept_proposals"].append({
                "project_name": parsed.get("project_name"),
                "developer": parsed.get("developer"),
                "date": parsed.get("date"),
                "folder_path": entry_path,
                "file_path": None,
            })
        else:
            ext = os.path.splitext(entry.lower())[1]
            if ext in (".pdf", ".pptx", ".docx", ".ppt"):
                parsed = parse_concept_proposal_file(entry)
                record["concept_proposals"].append({
                    "project_name": parsed.get("project_name"),
                    "developer": parsed.get("developer"),
                    "date": parsed.get("date"),
                    "folder_path": None,
                    "file_path": entry_path,
                })


def _recover_identity_from_manifest(
    hints: dict[str, Any], folder_path: str
) -> None:
    """Read identity tags from an existing artist_manifest.json so editorial
    data (identities, affiliations, locations, names, pronouns) survives rescans."""
    import json as _json

    manifest_path = os.path.join(folder_path, "artist_manifest.json")
    if not os.path.isfile(manifest_path):
        return
    try:
        with open(manifest_path, encoding="utf-8") as fh:
            data = _json.load(fh)
    except (OSError, ValueError):
        return

    # Skip reference manifests
    if data.get("manifest_type") == "reference":
        return

    identity = data.get("identity", {})
    tags = identity.get("identity_tags", {})

    existing_identities = {i for i in hints["identities"]}
    existing_aff_keys = {(a["name"], a["type"]) for a in hints["affiliations"]}
    existing_loc_keys = {(l["place"], l["type"]) for l in hints["locations"]}

    for ident in tags.get("identities", []):
        if ident not in existing_identities:
            existing_identities.add(ident)
            hints["identities"].append(ident)

    for aff in tags.get("affiliations", []):
        key = (aff.get("name", ""), aff.get("type", "nation"))
        if key not in existing_aff_keys:
            existing_aff_keys.add(key)
            hints["affiliations"].append({"name": key[0], "type": key[1]})

    for loc in tags.get("locations", []):
        key = (loc.get("place", ""), loc.get("type", "origin"))
        if key not in existing_loc_keys:
            existing_loc_keys.add(key)
            hints["locations"].append({"place": key[0], "type": key[1]})

    # Recover names
    existing_names = hints.setdefault("names", [])
    existing_name_keys = {(n["name"], n["type"]) for n in existing_names}
    for ne in identity.get("names", []):
        key = (ne.get("name", ""), ne.get("type", "pseudonym"))
        if key not in existing_name_keys:
            existing_name_keys.add(key)
            existing_names.append({"name": key[0], "type": key[1]})

    pronouns = identity.get("pronouns")
    if pronouns and "pronouns" not in hints:
        hints["pronouns"] = pronouns

    career_stage = identity.get("career_stage")
    if career_stage and "career_stage" not in hints:
        hints["career_stage"] = career_stage


def _find_primary_doc(folder_path: str) -> str | None:
    """Find the main document in a folder (first PDF, then first DOCX)."""
    pdfs = []
    docxs = []
    try:
        for f in sorted(os.listdir(folder_path)):
            fpath = os.path.join(folder_path, f)
            if os.path.isfile(fpath):
                ext = os.path.splitext(f.lower())[1]
                if ext == ".pdf":
                    pdfs.append(fpath)
                elif ext in (".docx", ".doc"):
                    docxs.append(fpath)
    except PermissionError:
        pass
    return pdfs[0] if pdfs else (docxs[0] if docxs else None)
