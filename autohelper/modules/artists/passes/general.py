"""
General-purpose domain pass.

A single class that handles any category (indigenous, public, private, corporate)
using layout config from the lexicon.  Replaces IndigenousPass and StubPass.

Also scans non-artist (admin) folders and attempts to attribute their files
to known artists by name matching.
"""
from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from ..config import DEFAULT_DOMAIN_CONFIGS, DomainConfig, get_lexicon, is_artist_folder
from ..scanner import scan_artist_folder
from ..utils import classify_file, normalize_name

logger = logging.getLogger(__name__)


class GeneralPass:
    """Scans one category directory using its configured layout."""

    def __init__(self, category_key: str) -> None:
        self._category_key = category_key
        self.admin_files: list[dict[str, Any]] = []

    @property
    def domain_key(self) -> str:
        return self._category_key

    @property
    def label(self) -> str:
        lex = get_lexicon()
        cat = next((c for c in lex.categories if c.key == self._category_key), None)
        return cat.label if cat else self._category_key

    def _get_domain_config(self) -> DomainConfig:
        lex = get_lexicon()
        return lex.domain_configs.get(
            self._category_key,
            DEFAULT_DOMAIN_CONFIGS.get(
                self._category_key,
                DomainConfig(key=self._category_key),
            ),
        )

    def execute(
        self,
        storage_root: Path,
        progress_cb: Callable[[str], None],
        cancel: threading.Event | None = None,
    ) -> list[dict[str, Any]]:
        lex = get_lexicon()
        cat = next((c for c in lex.categories if c.key == self._category_key), None)
        if not cat:
            return []

        domain_cfg = self._get_domain_config()
        cat_path = storage_root / cat.rel_path
        if not cat_path.is_dir():
            progress_cb(f"[{cat.label}] Path not found: {cat_path}")
            return []

        progress_cb(f"[{cat.label}] Scanning {cat_path}")

        if cat.layout == "nation_based":
            records, skipped = self._scan_nation_based(cat_path, cat.key, progress_cb, cancel)
        elif cat.layout == "bucketed":
            records, skipped = self._scan_bucketed(cat_path, cat.key, progress_cb, cancel)
        elif cat.layout == "flat":
            records, skipped = self._scan_flat(cat_path, cat.key, progress_cb, cancel)
        else:
            progress_cb(f"[{cat.label}] Unknown layout: {cat.layout}")
            return []

        progress_cb(f"[{cat.label}] {len(records)} folders")

        # Stamp domain metadata
        for rec in records:
            rec["domain_source"] = self._category_key
            rec["confidence"] = domain_cfg.confidence
            rec["validation_flags"] = []
            rec["ground_truth_match"] = None
            rec["contact_enrichment"] = {}

        # Scan admin folders for files attributable to known artists
        if skipped and not (cancel and cancel.is_set()):
            admin = self._scan_admin_folders(
                skipped, records, cat.key, progress_cb, cancel,
            )
            self.admin_files.extend(admin)
            if admin:
                progress_cb(f"[{cat.label}] {len(admin)} admin files found")

        return records

    # ------------------------------------------------------------------
    # Layout walkers
    # ------------------------------------------------------------------

    def _scan_nation_based(
        self,
        cat_path: Path,
        category: str,
        emit: Callable[[str], None],
        cancel: threading.Event | None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Walk <Nation>/<ArtistFolder>/ structure. Returns (records, skipped_folders)."""
        lex = get_lexicon()
        domain_cfg = self._get_domain_config()
        extra_ignore = set(domain_cfg.extra_ignore_dirs)
        records: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []

        try:
            nations = sorted(os.listdir(cat_path))
        except PermissionError:
            return records, skipped

        for nation in nations:
            if cancel and cancel.is_set():
                break
            nation_path = os.path.join(cat_path, nation)
            if not os.path.isdir(nation_path):
                continue
            if nation.lower() in lex.ignore_dirs or nation.lower() in extra_ignore:
                continue

            emit(f"  [{category}] {nation}")

            try:
                artist_folders = sorted(os.listdir(nation_path))
            except PermissionError:
                continue

            for folder in artist_folders:
                artist_path = os.path.join(nation_path, folder)
                if not os.path.isdir(artist_path) or folder.lower() in lex.ignore_dirs:
                    continue
                if not is_artist_folder(folder):
                    logger.debug("Skipping non-artist folder: %s/%s/%s", category, nation, folder)
                    skipped.append({
                        "folder_name": folder,
                        "folder_path": artist_path,
                        "nation": nation,
                    })
                    continue
                records.append(scan_artist_folder(
                    category=category,
                    nation=nation,
                    folder_name=folder,
                    folder_path=artist_path,
                ))

        return records, skipped

    def _scan_bucketed(
        self,
        cat_path: Path,
        category: str,
        emit: Callable[[str], None],
        cancel: threading.Event | None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Walk <LetterBucket>/<ArtistFolder>/ structure. Returns (records, skipped_folders)."""
        lex = get_lexicon()
        domain_cfg = self._get_domain_config()
        extra_ignore = set(domain_cfg.extra_ignore_dirs)
        records: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []

        try:
            buckets = sorted(os.listdir(cat_path))
        except PermissionError:
            return records, skipped

        for bucket in buckets:
            if cancel and cancel.is_set():
                break
            if bucket.startswith("z_") or bucket.lower() in lex.ignore_dirs or bucket.lower() in extra_ignore:
                continue
            bucket_path = os.path.join(cat_path, bucket)
            if not os.path.isdir(bucket_path):
                continue

            emit(f"  [{category}] {bucket}")

            try:
                artist_folders = sorted(os.listdir(bucket_path))
            except PermissionError:
                continue

            for folder in artist_folders:
                if folder.startswith("a ") or folder.startswith("z_"):
                    continue
                artist_path = os.path.join(bucket_path, folder)
                if not os.path.isdir(artist_path):
                    continue
                if not is_artist_folder(folder):
                    logger.debug("Skipping non-artist folder: %s/%s/%s", category, bucket, folder)
                    skipped.append({
                        "folder_name": folder,
                        "folder_path": artist_path,
                        "nation": None,
                    })
                    continue
                records.append(scan_artist_folder(
                    category=category,
                    nation=None,
                    folder_name=folder,
                    folder_path=artist_path,
                ))

        return records, skipped

    def _scan_flat(
        self,
        cat_path: Path,
        category: str,
        emit: Callable[[str], None],
        cancel: threading.Event | None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Walk flat <ArtistFolder>/ structure. Returns (records, skipped_folders)."""
        lex = get_lexicon()
        domain_cfg = self._get_domain_config()
        extra_ignore = set(domain_cfg.extra_ignore_dirs)
        records: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []

        try:
            artist_folders = sorted(os.listdir(cat_path))
        except PermissionError:
            return records, skipped

        for folder in artist_folders:
            if cancel and cancel.is_set():
                break
            if folder.lower() in lex.ignore_dirs or folder.lower() in extra_ignore or folder.startswith("z_"):
                continue
            artist_path = os.path.join(cat_path, folder)
            if not os.path.isdir(artist_path):
                continue
            if not is_artist_folder(folder):
                logger.debug("Skipping non-artist folder: %s/%s", category, folder)
                skipped.append({
                    "folder_name": folder,
                    "folder_path": artist_path,
                    "nation": None,
                })
                continue
            records.append(scan_artist_folder(
                category=category,
                nation=None,
                folder_name=folder,
                folder_path=artist_path,
            ))

        return records, skipped

    # ------------------------------------------------------------------
    # Admin folder scanning
    # ------------------------------------------------------------------

    def _scan_admin_folders(
        self,
        skipped_folders: list[dict[str, Any]],
        records: list[dict[str, Any]],
        category: str,
        emit: Callable[[str], None],
        cancel: threading.Event | None,
    ) -> list[dict[str, Any]]:
        """Walk skipped (non-artist) folders, classify files, and try to
        match them to known artist records by name."""

        # Build lookup: normalized_name -> artist record
        name_index: dict[str, dict[str, Any]] = {}
        for rec in records:
            norm = normalize_name(rec.get("display_name", ""))
            if norm:
                name_index[norm] = rec
            # Also index by last_name for partial matching
            last = rec.get("last_name")
            if last:
                norm_last = normalize_name(last)
                if norm_last and norm_last not in name_index:
                    name_index[norm_last] = rec

        lex = get_lexicon()
        admin_files: list[dict[str, Any]] = []

        for sf in skipped_folders:
            if cancel and cancel.is_set():
                break

            folder_path = sf["folder_path"]
            folder_name = sf["folder_name"]
            nation = sf.get("nation")

            emit(f"  [{category}] Admin: {folder_name}")

            try:
                for root, dirs, files in os.walk(folder_path):
                    dirs[:] = [d for d in dirs if d.lower() not in lex.ignore_dirs]
                    for fname in files:
                        if fname.lower() in lex.ignore_files or fname.startswith("."):
                            continue
                        ftype = classify_file(fname)
                        if ftype == "ignore" or ftype == "other":
                            continue

                        fpath = os.path.join(root, fname)
                        candidate_id, match_score = self._match_file_to_artist(
                            fname, name_index,
                        )

                        if candidate_id and match_score and match_score >= 0.8:
                            # High-confidence match: append to the artist record
                            matched_rec = name_index.get(candidate_id)
                            if matched_rec and ftype == "document":
                                matched_rec.setdefault("loose_docs", []).append(fpath)
                            elif matched_rec and ftype == "bio":
                                matched_rec.setdefault("bios", []).append({
                                    "file_path": fpath, "date": None, "is_current": False,
                                })
                            elif matched_rec and ftype == "cv":
                                matched_rec.setdefault("cvs", []).append({
                                    "file_path": fpath, "date": None, "is_current": False,
                                })
                            # Exact match — don't add to unattributed
                            if match_score >= 1.0:
                                continue

                        admin_files.append({
                            "file_path": fpath,
                            "folder_name": folder_name,
                            "category": category,
                            "nation": nation,
                            "file_type": ftype,
                            "candidate_artist_id": (
                                name_index[candidate_id]["artist_id"]
                                if candidate_id and candidate_id in name_index
                                else None
                            ),
                            "match_score": match_score,
                        })
            except PermissionError:
                continue

        return admin_files

    def _match_file_to_artist(
        self,
        filename: str,
        name_index: dict[str, dict[str, Any]],
    ) -> tuple[str | None, float | None]:
        """Try to match a filename to a known artist. Returns (index_key, score)."""
        stem = os.path.splitext(filename)[0]
        # Remove common prefixes/suffixes like dates
        cleaned = stem.replace("_", " ").replace("-", " ")
        norm = normalize_name(cleaned)

        if not norm:
            return None, None

        # Exact match
        if norm in name_index:
            return norm, 1.0

        # Fuzzy match against all known names
        best_key: str | None = None
        best_score = 0.0
        for key in name_index:
            score = SequenceMatcher(None, norm, key).ratio()
            if score > best_score:
                best_score = score
                best_key = key

        if best_key and best_score > 0.8:
            return best_key, best_score

        return None, None
