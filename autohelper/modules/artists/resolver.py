"""
Artist resolver: groups folder records by canonical artist_id,
merges cross-category duplicates, enriches with contact data.

Returns a list of ResolvedArtist dicts ready for manifest generation.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from .config import CATEGORY_PRIORITY, get_lexicon
from .utils import normalize_name

logger = logging.getLogger(__name__)


def resolve_artists(
    folder_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Group folder records by canonical_id, merge data.

    Returns a list of ResolvedArtist dicts. Each dict describes one
    logical artist (which may span multiple folders/categories).
    """
    # Group records by canonical_id
    groups: dict[str, list[dict[str, Any]]] = {}
    for rec in folder_records:
        cid = rec["canonical_id"]
        groups.setdefault(cid, []).append(rec)

    resolved: list[dict[str, Any]] = []
    for cid, recs in sorted(groups.items()):
        artist = _merge_records(cid, recs)
        resolved.append(artist)

    logger.info(
        "Resolved %d folder records into %d unique artists",
        len(folder_records),
        len(resolved),
    )
    return resolved


def _merge_records(
    canonical_id: str,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Merge one or more folder records into a single ResolvedArtist dict."""
    lex = get_lexicon()
    multi_cfg = lex.multi_folder_artists.get(canonical_id)

    # Determine primary record by category priority
    primary_rec = _pick_primary(records, multi_cfg)

    # Build folder_locations list
    folder_locations = _build_folder_locations(records, primary_rec)

    # Merge file collections from all records (deduplicate by basename)
    bios = _merge_file_lists([r["bios"] for r in records])
    cvs = _merge_file_lists([r["cvs"] for r in records])
    tearsheets = _merge_file_lists([r["tearsheets"] for r in records])
    project_lists = _merge_file_lists([r["project_lists"] for r in records])
    eois = _merge_generic_lists([r["eois"] for r in records], "project_name")
    concept_proposals = _merge_generic_lists(
        [r["concept_proposals"] for r in records], "project_name"
    )

    # Images — deduplicate by basename
    all_image_paths: list[str] = []
    seen_basenames: set[str] = set()
    for rec in records:
        for p in rec["image_paths"]:
            bn = os.path.basename(p).lower()
            if bn not in seen_basenames:
                seen_basenames.add(bn)
                all_image_paths.append(p)

    # Website URLs
    website_urls: list[str] = []
    seen_urls: set[str] = set()
    for rec in records:
        for u in rec["website_urls"]:
            if u not in seen_urls:
                seen_urls.add(u)
                website_urls.append(u)

    # Review notes
    review_notes = list(primary_rec.get("review_notes", []))
    if multi_cfg and multi_cfg.get("review_note"):
        review_notes.append(multi_cfg["review_note"])
    nested_cfg = primary_rec.get("nested_cfg")
    if nested_cfg and nested_cfg.get("review_note"):
        review_notes.append(nested_cfg["review_note"])

    # Collaborative entity — members become affiliations
    collab_cfg = primary_rec.get("collab_cfg")

    # Display name
    display_name = primary_rec["display_name"]
    if collab_cfg:
        display_name = collab_cfg["display_name"]

    # Merge identity hints from all records
    merged_identity = _merge_identity_hints(records)

    # Inject collaborative members as affiliations
    if collab_cfg:
        existing_aff_keys = {(a["name"], a["type"]) for a in merged_identity["affiliations"]}
        for member in collab_cfg.get("members", []):
            key = (member, "collective")
            if key not in existing_aff_keys:
                existing_aff_keys.add(key)
                merged_identity["affiliations"].append({"name": member, "type": "collective"})

    # Inject alternative names (spelling variants) and traditional name
    names: list[dict[str, str]] = list(merged_identity.get("names", []))
    existing_name_keys = {(n["name"], n["type"]) for n in names}
    folder_display_names = {r["display_name"] for r in records}
    for dn in sorted(folder_display_names):
        if dn != display_name:
            key = (dn, "pseudonym")
            if key not in existing_name_keys:
                existing_name_keys.add(key)
                names.append({"name": dn, "type": "pseudonym"})
    nested_cfg = primary_rec.get("nested_cfg")
    if nested_cfg and nested_cfg.get("traditional_name"):
        key = (nested_cfg["traditional_name"], "traditional")
        if key not in existing_name_keys:
            existing_name_keys.add(key)
            names.append({"name": nested_cfg["traditional_name"], "type": "traditional"})
    merged_identity["names"] = names

    # Collect categories
    categories = sorted({r["category"] for r in records})

    # Propagate ground truth contact enrichment (first match wins)
    contact_enrichment: dict[str, Any] = {}
    ground_truth_match = None
    for rec in records:
        ce = rec.get("contact_enrichment")
        if ce:
            for k, v in ce.items():
                if k not in contact_enrichment and v:
                    contact_enrichment[k] = v
        if not ground_truth_match and rec.get("ground_truth_match"):
            ground_truth_match = rec["ground_truth_match"]

    # Merge validation flags
    all_validation_flags: list[str] = []
    seen_flags: set[str] = set()
    for rec in records:
        for flag in rec.get("validation_flags", []):
            if flag not in seen_flags:
                seen_flags.add(flag)
                all_validation_flags.append(flag)

    return {
        "artist_id": canonical_id,
        "display_name": display_name,
        "first_name": primary_rec["first_name"],
        "last_name": primary_rec["last_name"],
        "categories": categories,
        "folder_locations": folder_locations,
        "primary_folder_path": primary_rec["folder_path"],
        "bios": bios,
        "cvs": cvs,
        "tearsheets": tearsheets,
        "project_lists": project_lists,
        "eois": eois,
        "concept_proposals": concept_proposals,
        "image_paths": all_image_paths,
        "image_count": len(all_image_paths),
        "website_urls": website_urls,
        "review_notes": [n for n in review_notes if n],
        "identity_hints": merged_identity,
        "secondary_folders": [
            fl for fl in folder_locations if not fl["is_primary"]
        ],
        "contact_enrichment": contact_enrichment,
        "ground_truth_match": ground_truth_match,
        "validation_flags": all_validation_flags,
    }


def _pick_primary(
    records: list[dict[str, Any]],
    multi_cfg: dict | None,
) -> dict[str, Any]:
    """Pick the primary record based on multi-folder config or category priority."""
    if multi_cfg:
        primary_cat = multi_cfg.get("primary", "indigenous")
        for rec in records:
            if rec["category"] == primary_cat:
                return rec

    # Sort by category priority, pick first
    def _priority(rec: dict) -> int:
        try:
            return CATEGORY_PRIORITY.index(rec["category"])
        except ValueError:
            return 999

    return sorted(records, key=_priority)[0]


def _build_folder_locations(
    records: list[dict[str, Any]],
    primary_rec: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build the folder_locations list with is_primary flags."""
    locations = []
    seen_paths: set[str] = set()

    for rec in records:
        path = rec["folder_path"]
        if path in seen_paths:
            continue
        seen_paths.add(path)
        locations.append({
            "category": rec["category"],
            "folder_path": path,
            "nation": rec.get("nation"),
            "is_primary": (path == primary_rec["folder_path"]),
        })

    return locations


def _merge_file_lists(lists: list[list[dict]]) -> list[dict]:
    """Merge file-entry lists, deduplicating by basename."""
    merged = []
    seen: set[str] = set()
    for lst in lists:
        for entry in lst:
            bn = os.path.basename(entry.get("file_path", "")).lower()
            if bn and bn not in seen:
                seen.add(bn)
                merged.append(entry)
    return merged


def _merge_generic_lists(lists: list[list[dict]], dedup_key: str) -> list[dict]:
    """Merge lists of dicts, deduplicating by a key field."""
    merged = []
    seen: set[str] = set()
    for lst in lists:
        for entry in lst:
            val = entry.get(dedup_key) or entry.get("file_path") or ""
            key = normalize_name(str(val))
            if key not in seen:
                seen.add(key)
                merged.append(entry)
    return merged


def _merge_identity_hints(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge identity_hints dicts from all folder records for one artist."""
    merged: dict[str, Any] = {
        "identities": [],
        "affiliations": [],
        "locations": [],
        "names": [],
    }
    seen_identities: set[str] = set()
    seen_affs: set[tuple[str, str]] = set()
    seen_locs: set[tuple[str, str]] = set()
    seen_names: set[tuple[str, str]] = set()

    for rec in records:
        hints = rec.get("identity_hints", {})

        for ident in hints.get("identities", []):
            if ident not in seen_identities:
                seen_identities.add(ident)
                merged["identities"].append(ident)

        for aff in hints.get("affiliations", []):
            key = (aff["name"], aff["type"])
            if key not in seen_affs:
                seen_affs.add(key)
                merged["affiliations"].append(aff)

        for loc in hints.get("locations", []):
            key = (loc["place"], loc["type"])
            if key not in seen_locs:
                seen_locs.add(key)
                merged["locations"].append(loc)

        for name in hints.get("names", []):
            key = (name["name"], name["type"])
            if key not in seen_names:
                seen_names.add(key)
                merged["names"].append(name)

        # First-wins for scalar fields
        if hints.get("pronouns") and "pronouns" not in merged:
            merged["pronouns"] = hints["pronouns"]
        if hints.get("career_stage") and "career_stage" not in merged:
            merged["career_stage"] = hints["career_stage"]

    return merged
