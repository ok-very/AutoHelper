"""
Comprehensive reconciliation engine: surfaces data quality issues across
all artist record fields — engagement pipeline, identities, affiliations,
names/aliases, locations, and potential duplicates.

Reports:
  Engagement:
  - orphan_eois: EOI entries not linked to any project pipeline record
  - orphan_proposals: concept proposals not linked to any project
  - stalled_projects: projects stuck at a stage
  - fuzzy_matches: EOI/proposal names that approximately match a project name
  - panel_gaps: artists who served on panels but have no project records

  Data quality:
  - duplicate_artists: artists with very similar display names (possible dupes)
  - affiliation_variants: near-match affiliation names across all artists
  - identity_inconsistencies: near-duplicate identity tags across the corpus
  - alias_conflicts: multiple artists sharing the same name entry
  - location_variants: near-match location place names across artists
"""
from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any

from autohelper.db import get_db

logger = logging.getLogger(__name__)


def _normalize(s: str) -> str:
    """Lowercase, strip, collapse whitespace."""
    return " ".join(s.lower().split())


def _similarity(a: str, b: str) -> float:
    """Normalized string similarity (0-1)."""
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


# ------------------------------------------------------------------
# Report builder
# ------------------------------------------------------------------

def get_reconciliation_report() -> dict[str, Any]:
    """Build the full reconciliation report from all cached artist manifests."""
    db = get_db()

    try:
        rows = db.execute(
            "SELECT artist_id, display_name, manifest_json FROM artists"
        ).fetchall()
    except Exception:
        return _empty_report()

    # Parse all manifests once
    artists: list[tuple[str, str, dict]] = []
    for artist_id, display_name, manifest_json in rows:
        if not manifest_json:
            continue
        try:
            m = json.loads(manifest_json)
        except (json.JSONDecodeError, TypeError):
            continue
        artists.append((artist_id, display_name, m))

    report = {}

    # Engagement reconciliation
    report.update(_engagement_report(artists))

    # Data quality reconciliation
    report.update(_data_quality_report(artists))

    return report


def _empty_report() -> dict[str, list]:
    return {
        "orphan_eois": [], "orphan_proposals": [],
        "stalled_projects": [], "fuzzy_matches": [], "panel_gaps": [],
        "duplicate_artists": [], "affiliation_variants": [],
        "identity_inconsistencies": [], "alias_conflicts": [],
        "location_variants": [],
    }


# ------------------------------------------------------------------
# Engagement pipeline reconciliation
# ------------------------------------------------------------------

def _engagement_report(artists: list[tuple[str, str, dict]]) -> dict[str, list]:
    orphan_eois: list[dict] = []
    orphan_proposals: list[dict] = []
    stalled_projects: list[dict] = []
    fuzzy_matches: list[dict] = []
    panel_gaps: list[dict] = []

    for artist_id, display_name, m in artists:
        eng = m.get("engagement", {})
        projects = eng.get("public_art_projects", [])
        eois = eng.get("eois", [])
        proposals = eng.get("concept_proposals", [])
        panel_history = eng.get("panel_history", [])

        project_names = {
            _normalize(p["project_name"])
            for p in projects if p.get("project_name")
        }

        # Orphan EOIs
        for eoi in eois:
            eoi_name = eoi.get("project_name") or ""
            if not eoi_name:
                continue
            norm_eoi = _normalize(eoi_name)
            if norm_eoi not in project_names:
                best_score, best_match = _best_fuzzy(norm_eoi, project_names)
                if best_score >= 0.7:
                    fuzzy_matches.append({
                        "artist_id": artist_id,
                        "display_name": display_name,
                        "type": "eoi",
                        "source_name": eoi_name,
                        "match_name": best_match,
                        "score": round(best_score, 2),
                    })
                else:
                    orphan_eois.append({
                        "artist_id": artist_id,
                        "display_name": display_name,
                        "project_name": eoi_name,
                        "file_path": eoi.get("file_path"),
                    })

        # Orphan proposals
        for prop in proposals:
            prop_name = prop.get("project_name") or ""
            if not prop_name:
                continue
            norm_prop = _normalize(prop_name)
            if norm_prop not in project_names:
                best_score, best_match = _best_fuzzy(norm_prop, project_names)
                if best_score >= 0.7:
                    fuzzy_matches.append({
                        "artist_id": artist_id,
                        "display_name": display_name,
                        "type": "proposal",
                        "source_name": prop_name,
                        "match_name": best_match,
                        "score": round(best_score, 2),
                    })
                else:
                    orphan_proposals.append({
                        "artist_id": artist_id,
                        "display_name": display_name,
                        "project_name": prop_name,
                        "developer": prop.get("developer"),
                    })

        # Stalled projects
        for i, proj in enumerate(projects):
            status = proj.get("status", "submitted")
            if status in ("awarded",) and not proj.get("status_date"):
                stalled_projects.append({
                    "artist_id": artist_id,
                    "display_name": display_name,
                    "project_name": proj["project_name"],
                    "status": status,
                    "project_index": i,
                })

        # Panel gaps
        if panel_history and not projects:
            panel_gaps.append({
                "artist_id": artist_id,
                "display_name": display_name,
                "panel_count": len(panel_history),
            })

    return {
        "orphan_eois": orphan_eois,
        "orphan_proposals": orphan_proposals,
        "stalled_projects": stalled_projects,
        "fuzzy_matches": fuzzy_matches,
        "panel_gaps": panel_gaps,
    }


def _best_fuzzy(needle: str, haystack: set[str]) -> tuple[float, str]:
    best_score = 0.0
    best_match = ""
    for h in haystack:
        score = _similarity(needle, h)
        if score > best_score:
            best_score = score
            best_match = h
    return best_score, best_match


# ------------------------------------------------------------------
# Data quality reconciliation
# ------------------------------------------------------------------

def _data_quality_report(artists: list[tuple[str, str, dict]]) -> dict[str, list]:
    duplicate_artists = _find_duplicate_artists(artists)
    affiliation_variants = _find_affiliation_variants(artists)
    identity_inconsistencies = _find_identity_inconsistencies(artists)
    alias_conflicts = _find_alias_conflicts(artists)
    location_variants = _find_location_variants(artists)

    return {
        "duplicate_artists": duplicate_artists,
        "affiliation_variants": affiliation_variants,
        "identity_inconsistencies": identity_inconsistencies,
        "alias_conflicts": alias_conflicts,
        "location_variants": location_variants,
    }


def _find_duplicate_artists(
    artists: list[tuple[str, str, dict]],
) -> list[dict]:
    """Find artists with very similar display names."""
    results: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for i, (id_a, name_a, _) in enumerate(artists):
        if not name_a:
            continue
        for j in range(i + 1, len(artists)):
            id_b, name_b, _ = artists[j]
            if not name_b:
                continue
            pair = (min(id_a, id_b), max(id_a, id_b))
            if pair in seen:
                continue
            score = _similarity(name_a, name_b)
            if score >= 0.85 and _normalize(name_a) != _normalize(name_b):
                seen.add(pair)
                results.append({
                    "artist_id_a": id_a,
                    "name_a": name_a,
                    "artist_id_b": id_b,
                    "name_b": name_b,
                    "score": round(score, 2),
                })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:100]


def _find_affiliation_variants(
    artists: list[tuple[str, str, dict]],
) -> list[dict]:
    """Find near-match affiliation names across all artists."""
    # Collect all affiliation names → set of artist_ids using them
    aff_map: dict[str, set[str]] = defaultdict(set)
    aff_original: dict[str, str] = {}  # normalized → first original form

    for artist_id, _, m in artists:
        tags = m.get("identity", {}).get("identity_tags", {})
        for aff in tags.get("affiliations", []):
            name = aff.get("name", "")
            if not name:
                continue
            norm = _normalize(name)
            aff_map[norm].add(artist_id)
            if norm not in aff_original:
                aff_original[norm] = name

    return _find_string_variants(aff_map, aff_original, "affiliation")


def _find_identity_inconsistencies(
    artists: list[tuple[str, str, dict]],
) -> list[dict]:
    """Find near-duplicate identity tags across the corpus."""
    id_map: dict[str, set[str]] = defaultdict(set)
    id_original: dict[str, str] = {}

    for artist_id, _, m in artists:
        tags = m.get("identity", {}).get("identity_tags", {})
        for ident in tags.get("identities", []):
            if not ident:
                continue
            norm = _normalize(ident)
            id_map[norm].add(artist_id)
            if norm not in id_original:
                id_original[norm] = ident

    return _find_string_variants(id_map, id_original, "identity")


def _find_location_variants(
    artists: list[tuple[str, str, dict]],
) -> list[dict]:
    """Find near-match location place names across artists."""
    loc_map: dict[str, set[str]] = defaultdict(set)
    loc_original: dict[str, str] = {}

    for artist_id, _, m in artists:
        tags = m.get("identity", {}).get("identity_tags", {})
        for loc in tags.get("locations", []):
            place = loc.get("place", "")
            if not place:
                continue
            norm = _normalize(place)
            loc_map[norm].add(artist_id)
            if norm not in loc_original:
                loc_original[norm] = place

    return _find_string_variants(loc_map, loc_original, "location")


def _find_string_variants(
    value_map: dict[str, set[str]],
    original_map: dict[str, str],
    field_type: str,
) -> list[dict]:
    """Generic: find pairs of normalized strings that are similar but not identical."""
    results: list[dict] = []
    keys = sorted(value_map.keys())
    seen: set[tuple[str, str]] = set()

    for i, key_a in enumerate(keys):
        for j in range(i + 1, len(keys)):
            key_b = keys[j]
            if key_a == key_b:
                continue
            pair = (key_a, key_b)
            if pair in seen:
                continue
            score = _similarity(key_a, key_b)
            if score >= 0.75:
                seen.add(pair)
                results.append({
                    "type": field_type,
                    "value_a": original_map[key_a],
                    "value_b": original_map[key_b],
                    "count_a": len(value_map[key_a]),
                    "count_b": len(value_map[key_b]),
                    "score": round(score, 2),
                })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:100]


def _find_alias_conflicts(
    artists: list[tuple[str, str, dict]],
) -> list[dict]:
    """Find artists who share the same name entry (alias/pseudonym/trade name)."""
    # Map normalized name → list of (artist_id, display_name, name_type)
    name_map: dict[str, list[tuple[str, str, str, str]]] = defaultdict(list)

    for artist_id, display_name, m in artists:
        identity = m.get("identity", {})
        for name_entry in identity.get("names", []):
            name = name_entry.get("name", "")
            ntype = name_entry.get("type", "pseudonym")
            if not name:
                continue
            norm = _normalize(name)
            name_map[norm].append((artist_id, display_name, name, ntype))

    results: list[dict] = []
    for norm, entries in name_map.items():
        if len(entries) < 2:
            continue
        # Deduplicate by artist_id
        unique = {e[0]: e for e in entries}
        if len(unique) < 2:
            continue
        artists_list = [
            {"artist_id": e[0], "display_name": e[1], "name": e[2], "type": e[3]}
            for e in unique.values()
        ]
        results.append({
            "shared_name": entries[0][2],
            "artists": artists_list,
        })

    return results[:100]


# ------------------------------------------------------------------
# Resolve actions
# ------------------------------------------------------------------

def resolve_reconciliation_item(body: dict[str, Any]) -> None:
    """Execute a reconciliation action."""
    from .service import get_artist_service

    action = body.get("action")
    artist_id = body.get("artist_id", "")
    svc = get_artist_service()

    if action == "link_eoi":
        svc.add_project(artist_id, {
            "project_name": body.get("project_name", ""),
            "status": "submitted",
            "eoi_ref": body.get("eoi_name"),
        })

    elif action == "advance_status":
        project_index = body.get("project_index", -1)
        new_status = body.get("new_status", "completed")
        svc.update_project_status(artist_id, project_index, new_status)

    elif action in ("merge_affiliation", "merge_identity", "merge_location"):
        _merge_field_value(action, body)

    elif action == "dismiss":
        pass  # Frontend removes the item

    elif action == "assign_alias":
        _assign_alias(body)

    elif action == "remove_alias":
        _remove_alias(body)

    else:
        logger.warning("Unknown reconciliation action: %s", action)


def _assign_alias(body: dict[str, Any]) -> None:
    """Move a NameEntry from one artist to another."""
    from .service import get_artist_service

    from_id = body.get("from_artist_id", "")
    to_id = body.get("to_artist_id", "")
    name = body.get("name", "")
    if not from_id or not to_id or not name:
        return

    svc = get_artist_service()
    db = get_db()
    norm_name = _normalize(name)

    # Load both manifests
    for aid, role in [(from_id, "from"), (to_id, "to")]:
        row = db.execute(
            "SELECT manifest_json FROM artists WHERE artist_id = ?", (aid,)
        ).fetchone()
        if not row:
            return
        if role == "from":
            from_manifest = json.loads(row[0])
        else:
            to_manifest = json.loads(row[0])

    # Remove matching name from source
    from_names = from_manifest.get("identity", {}).get("names", [])
    moved_entry = None
    new_from_names = []
    for entry in from_names:
        if _normalize(entry.get("name", "")) == norm_name and moved_entry is None:
            moved_entry = entry
        else:
            new_from_names.append(entry)

    if not moved_entry:
        return

    from_manifest.setdefault("identity", {})["names"] = new_from_names

    # Add to target
    to_names = to_manifest.get("identity", {}).get("names", [])
    # Don't add if already exists
    if not any(_normalize(e.get("name", "")) == norm_name for e in to_names):
        to_names.append(moved_entry)
    to_manifest.setdefault("identity", {})["names"] = to_names

    svc.save_manifest(from_id, from_manifest)
    svc.save_manifest(to_id, to_manifest)


def _remove_alias(body: dict[str, Any]) -> None:
    """Remove a NameEntry from an artist."""
    from .service import get_artist_service

    artist_id = body.get("artist_id", "")
    name = body.get("name", "")
    if not artist_id or not name:
        return

    svc = get_artist_service()
    db = get_db()
    norm_name = _normalize(name)

    row = db.execute(
        "SELECT manifest_json FROM artists WHERE artist_id = ?", (artist_id,)
    ).fetchone()
    if not row:
        return

    manifest = json.loads(row[0])
    names = manifest.get("identity", {}).get("names", [])
    new_names = [e for e in names if _normalize(e.get("name", "")) != norm_name]

    if len(new_names) == len(names):
        return  # Nothing removed

    manifest.setdefault("identity", {})["names"] = new_names
    svc.save_manifest(artist_id, manifest)


def _merge_field_value(action: str, body: dict[str, Any]) -> None:
    """Standardize a field value across all artists that use the variant."""
    from .service import get_artist_service

    old_value = body.get("old_value", "")
    new_value = body.get("new_value", "")
    if not old_value or not new_value:
        return

    svc = get_artist_service()
    db = get_db()

    try:
        rows = db.execute(
            "SELECT artist_id, manifest_json FROM artists WHERE manifest_json IS NOT NULL"
        ).fetchall()
    except Exception:
        return

    norm_old = _normalize(old_value)

    for artist_id, manifest_json in rows:
        try:
            m = json.loads(manifest_json)
        except (json.JSONDecodeError, TypeError):
            continue

        tags = m.get("identity", {}).get("identity_tags", {})
        changed = False

        if action == "merge_affiliation":
            for aff in tags.get("affiliations", []):
                if _normalize(aff.get("name", "")) == norm_old:
                    aff["name"] = new_value
                    changed = True

        elif action == "merge_identity":
            identities = tags.get("identities", [])
            for i, ident in enumerate(identities):
                if _normalize(ident) == norm_old:
                    identities[i] = new_value
                    changed = True

        elif action == "merge_location":
            for loc in tags.get("locations", []):
                if _normalize(loc.get("place", "")) == norm_old:
                    loc["place"] = new_value
                    changed = True

        if changed:
            svc.save_manifest(artist_id, m)


# ------------------------------------------------------------------
# Merge artists
# ------------------------------------------------------------------

def merge_artists(keep_id: str, remove_id: str) -> dict[str, Any]:
    """
    Merge two artist records: fold remove into keep.

    - Union names, identity_tags, engagement, documents, folder_locations, images
    - Prefer keep's contact info, fill blanks from remove
    - Add remove's display_name as pseudonym if different
    - Delete remove from DB, write reference_manifest in remove's folder(s)
    """
    from .service import get_artist_service

    svc = get_artist_service()
    db = get_db()

    keep_row = db.execute(
        "SELECT manifest_json, primary_folder FROM artists WHERE artist_id = ?",
        (keep_id,),
    ).fetchone()
    remove_row = db.execute(
        "SELECT manifest_json, primary_folder FROM artists WHERE artist_id = ?",
        (remove_id,),
    ).fetchone()

    if not keep_row or not remove_row:
        raise ValueError(f"Artist not found: {keep_id if not keep_row else remove_id}")

    keep = json.loads(keep_row[0])
    remove = json.loads(remove_row[0])

    # --- names: union, dedup by normalized name ---
    keep_names = keep.get("identity", {}).get("names", [])
    remove_names = remove.get("identity", {}).get("names", [])
    seen_names = {_normalize(n.get("name", "")) for n in keep_names}
    for n in remove_names:
        norm = _normalize(n.get("name", ""))
        if norm and norm not in seen_names:
            keep_names.append(n)
            seen_names.add(norm)

    # Add remove's display_name as pseudonym if different
    keep_display = _normalize(keep.get("identity", {}).get("display_name", ""))
    remove_display = remove.get("identity", {}).get("display_name", "")
    if remove_display and _normalize(remove_display) != keep_display and _normalize(remove_display) not in seen_names:
        keep_names.append({"name": remove_display, "type": "pseudonym"})

    keep.setdefault("identity", {})["names"] = keep_names

    # --- identity_tags: union identities, affiliations, locations ---
    keep_tags = keep.get("identity", {}).get("identity_tags", {})
    remove_tags = remove.get("identity", {}).get("identity_tags", {})

    # identities (list of strings)
    keep_ids = set(keep_tags.get("identities", []))
    for ident in remove_tags.get("identities", []):
        keep_ids.add(ident)
    keep_tags["identities"] = sorted(keep_ids)

    # affiliations (list of dicts)
    keep_affs = keep_tags.get("affiliations", [])
    seen_affs = {_normalize(a.get("name", "")) for a in keep_affs}
    for aff in remove_tags.get("affiliations", []):
        norm = _normalize(aff.get("name", ""))
        if norm and norm not in seen_affs:
            keep_affs.append(aff)
            seen_affs.add(norm)
    keep_tags["affiliations"] = keep_affs

    # locations (list of dicts)
    keep_locs = keep_tags.get("locations", [])
    seen_locs = {_normalize(l.get("place", "")) for l in keep_locs}
    for loc in remove_tags.get("locations", []):
        norm = _normalize(loc.get("place", ""))
        if norm and norm not in seen_locs:
            keep_locs.append(loc)
            seen_locs.add(norm)
    keep_tags["locations"] = keep_locs

    keep.setdefault("identity", {})["identity_tags"] = keep_tags

    # --- engagement: concatenate panels, projects, eois, proposals ---
    keep_eng = keep.get("engagement", {})
    remove_eng = remove.get("engagement", {})

    for key in ("panel_history", "public_art_projects", "eois", "concept_proposals"):
        keep_list = keep_eng.get(key, [])
        remove_list = remove_eng.get(key, [])
        keep_eng[key] = keep_list + remove_list

    if "panel_count" in keep_eng or "panel_count" in remove_eng:
        keep_eng["panel_count"] = len(keep_eng.get("panel_history", []))

    keep["engagement"] = keep_eng

    # --- documents: union by file basename ---
    keep_docs = keep.get("documents", {})
    remove_docs = remove.get("documents", {})
    for doc_type in ("bios", "cvs", "tearsheets", "project_lists"):
        keep_entries = keep_docs.get(doc_type, [])
        seen_basenames = {
            os.path.basename(d.get("file_path", "")).lower()
            for d in keep_entries
            if d.get("file_path")
        }
        for entry in remove_docs.get(doc_type, []):
            fp = entry.get("file_path", "")
            if fp and os.path.basename(fp).lower() not in seen_basenames:
                keep_entries.append(entry)
                seen_basenames.add(os.path.basename(fp).lower())
        keep_docs[doc_type] = keep_entries
    keep["documents"] = keep_docs

    # --- folder_locations: keep all, preserve keep's primary ---
    keep_folders = keep.get("folder_locations", [])
    keep_paths = {f.get("folder_path", "").lower() for f in keep_folders}
    for fl in remove.get("folder_locations", []):
        if fl.get("folder_path", "").lower() not in keep_paths:
            fl["is_primary"] = False  # Don't let remove's primary override
            keep_folders.append(fl)
    keep["folder_locations"] = keep_folders

    # --- contact: prefer keep's non-empty, fill blanks from remove ---
    keep_contact = keep.get("contact", {})
    remove_contact = remove.get("contact", {})
    for field in ("email", "phone", "website", "notes"):
        if not keep_contact.get(field) and remove_contact.get(field):
            keep_contact[field] = remove_contact[field]
    keep["contact"] = keep_contact

    # --- images: union folder_paths ---
    keep_images = keep.get("images", {})
    remove_images = remove.get("images", {})
    keep_img_paths = set(keep_images.get("folder_paths", []))
    for p in remove_images.get("folder_paths", []):
        keep_img_paths.add(p)
    keep_images["folder_paths"] = sorted(keep_img_paths)
    keep_images["count"] = keep_images.get("count", 0) + remove_images.get("count", 0)
    keep["images"] = keep_images

    # --- _review_notes: concatenate ---
    keep_notes = keep.get("_review_notes", [])
    remove_notes = remove.get("_review_notes", [])
    keep["_review_notes"] = keep_notes + remove_notes

    # Save merged manifest
    svc.save_manifest(keep_id, keep)

    # Update artist_folders to point to keep_id
    try:
        db.execute(
            "UPDATE artist_folders SET artist_id = ? WHERE artist_id = ?",
            (keep_id, remove_id),
        )
    except Exception:
        pass  # Table may not exist

    # Delete remove artist from DB
    db.execute("DELETE FROM artists WHERE artist_id = ?", (remove_id,))
    db.commit()

    # Write reference_manifest.json in remove's folder(s)
    remove_primary = remove_row[1]
    if remove_primary and os.path.isdir(remove_primary):
        ref = {"merged_into": keep_id, "original_id": remove_id}
        ref_path = os.path.join(remove_primary, "reference_manifest.json")
        try:
            with open(ref_path, "w", encoding="utf-8") as fh:
                json.dump(ref, fh, indent=2)
        except OSError:
            logger.warning("Could not write reference_manifest.json to %s", remove_primary)

    logger.info("Merged artist %s into %s", remove_id, keep_id)
    return {"ok": True, "merged_manifest": keep}


def auto_merge(threshold: float = 0.95, dry_run: bool = True) -> dict[str, Any]:
    """
    Auto-merge duplicate artist pairs at or above the given similarity threshold.

    If dry_run, returns planned merges without executing.
    """
    report = get_reconciliation_report()
    duplicates = report.get("duplicate_artists", [])

    # Get completeness scores for all artists
    db = get_db()
    completeness: dict[str, float] = {}
    try:
        rows = db.execute(
            "SELECT artist_id, manifest_json FROM artists WHERE manifest_json IS NOT NULL"
        ).fetchall()
        for artist_id, manifest_json in rows:
            try:
                m = json.loads(manifest_json)
                completeness[artist_id] = m.get("completeness", {}).get("score", 0.0)
            except (json.JSONDecodeError, TypeError):
                completeness[artist_id] = 0.0
    except Exception:
        pass

    pairs = []
    for dup in duplicates:
        if dup["score"] < threshold:
            continue
        id_a = dup["artist_id_a"]
        id_b = dup["artist_id_b"]
        score_a = completeness.get(id_a, 0.0)
        score_b = completeness.get(id_b, 0.0)
        keep_id = id_a if score_a >= score_b else id_b
        remove_id = id_b if keep_id == id_a else id_a
        pairs.append({
            "keep_id": keep_id,
            "keep_name": dup["name_a"] if keep_id == id_a else dup["name_b"],
            "keep_completeness": round(max(score_a, score_b), 2),
            "remove_id": remove_id,
            "remove_name": dup["name_b"] if keep_id == id_a else dup["name_a"],
            "remove_completeness": round(min(score_a, score_b), 2),
            "score": dup["score"],
        })

    if dry_run:
        return {"pairs": pairs, "merged": 0, "errors": []}

    merged = 0
    errors: list[str] = []
    for pair in pairs:
        try:
            merge_artists(pair["keep_id"], pair["remove_id"])
            merged += 1
        except Exception as e:
            errors.append(f"{pair['keep_name']} / {pair['remove_name']}: {e}")

    return {"pairs": pairs, "merged": merged, "errors": errors}
