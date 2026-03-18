"""
Manifest generator: builds ArtistManifest objects from resolved artist data,
computes completeness scores, writes JSON to disk.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from .config import MANIFEST_FILENAME, get_lexicon
from .models import (
    AffiliationEntry,
    ArtistManifest,
    Completeness,
    ConceptProposal,
    Contact,
    DocumentEntry,
    Documents,
    EOIEntry,
    Engagement,
    FolderLocation,
    Identity,
    IdentityTags,
    Images,
    LocationEntry,
    NameEntry,
    PanelEntry,
    ReferenceManifest,
)

logger = logging.getLogger(__name__)


def build_manifest(artist: dict[str, Any]) -> ArtistManifest:
    """Build an ArtistManifest from a resolved artist dict."""
    ts = datetime.now(timezone.utc).isoformat()
    lex = get_lexicon()

    # --- Identity ---
    hints = artist.get("identity_hints", {})

    names = [
        NameEntry(name=n["name"], type=n["type"])
        for n in hints.get("names", [])
    ]
    affiliations = [
        AffiliationEntry(name=a["name"], type=a["type"])
        for a in hints.get("affiliations", [])
    ]
    locations = [
        LocationEntry(place=l["place"], type=l["type"])
        for l in hints.get("locations", [])
    ]

    identity = Identity(
        display_name=artist["display_name"],
        first_name=artist.get("first_name"),
        last_name=artist.get("last_name"),
        names=names,
        pronouns=hints.get("pronouns") or artist.get("pronouns"),
        career_stage=hints.get("career_stage"),
        identity_tags=IdentityTags(
            identities=hints.get("identities", []),
            affiliations=affiliations,
            locations=locations,
        ),
    )

    # --- Contact (ground truth enrichment fills blanks) ---
    contact_data = artist.get("contact") or {}
    enrichment = artist.get("contact_enrichment") or {}

    email = contact_data.get("email") or enrichment.get("email")
    phone = contact_data.get("phone") or enrichment.get("phone")
    website = contact_data.get("website")
    if not website and artist.get("website_urls"):
        website = artist["website_urls"][0]

    contact = Contact(
        email=email,
        phone=phone,
        website=website,
        notes=contact_data.get("notes"),
    )

    # --- Folder locations ---
    folder_locations = [
        FolderLocation(
            category=fl["category"],
            folder_path=fl["folder_path"],
            nation=fl.get("nation"),
            is_primary=fl["is_primary"],
        )
        for fl in artist.get("folder_locations", [])
    ]

    # --- Documents ---
    def make_docs(raw_list: list[dict]) -> list[DocumentEntry]:
        return [
            DocumentEntry(
                file_path=item.get("file_path", ""),
                date=item.get("date"),
                is_current=item.get("is_current", True),
            )
            for item in raw_list
        ]

    bios = make_docs(artist.get("bios", []))
    _mark_most_recent_current(bios)

    cvs = make_docs(artist.get("cvs", []))
    _mark_most_recent_current(cvs)

    tearsheets = make_docs(artist.get("tearsheets", []))
    project_lists = make_docs(artist.get("project_lists", []))

    documents = Documents(
        bios=bios, cvs=cvs, tearsheets=tearsheets, project_lists=project_lists,
    )

    # --- Engagement ---
    eois = [
        EOIEntry(
            project_name=e.get("project_name"),
            folder_path=e.get("folder_path"),
            file_path=e.get("file_path"),
        )
        for e in artist.get("eois", [])
    ]
    concept_proposals = [
        ConceptProposal(
            project_name=p.get("project_name"),
            developer=p.get("developer"),
            date=p.get("date"),
            folder_path=p.get("folder_path"),
            file_path=p.get("file_path"),
        )
        for p in artist.get("concept_proposals", [])
    ]
    engagement = Engagement(eois=eois, concept_proposals=concept_proposals)

    # --- Images ---
    images = Images(
        count=artist.get("image_count", 0),
        folder_paths=_unique_image_folders(artist.get("image_paths", [])),
    )

    # --- Completeness ---
    completeness = compute_completeness(identity, contact, documents, images, lex)

    manifest = ArtistManifest(
        artist_id=artist["artist_id"],
        generated_at=ts,
        categories=artist.get("categories", []),
        identity=identity,
        contact=contact,
        folder_locations=folder_locations,
        documents=documents,
        engagement=engagement,
        images=images,
        completeness=completeness,
        **{"_review_notes": artist.get("review_notes", [])},
    )
    return manifest


def compute_completeness(
    identity: Identity,
    contact: Contact,
    documents: Documents,
    images: Images,
    lex: Any = None,
) -> Completeness:
    """Compute weighted completeness score."""
    if lex is None:
        lex = get_lexicon()

    flags = {
        "has_bio": bool(documents.bios),
        "has_cv": bool(documents.cvs),
        "has_tearsheet": bool(documents.tearsheets),
        "has_contact_email": bool(contact.email),
        "has_contact_phone": bool(contact.phone),
        "has_website": bool(contact.website),
        "has_images": images.count > 0,
        "has_pronouns": bool(identity.pronouns),
    }

    score = sum(
        lex.completeness_weights.get(k, 0) for k, v in flags.items() if v
    )
    gaps = [
        lex.completeness_gap_labels.get(k, k)
        for k, v in flags.items()
        if not v
    ]

    return Completeness(
        **flags,
        score=round(score, 3),
        gaps=gaps,
    )


def write_manifest_to_disk(manifest: ArtistManifest, artist: dict[str, Any]) -> list[str]:
    """Write manifest JSON to primary folder and reference stubs to secondaries."""
    written: list[str] = []

    primary_path = artist["primary_folder_path"]
    manifest_path = os.path.join(primary_path, MANIFEST_FILENAME)

    data = manifest.model_dump_json_friendly()
    _preserve_ai_enrichment(manifest_path, data)
    _write_json(manifest_path, data)
    written.append(manifest_path)

    # Reference manifests for secondary folders
    primary_category = next(
        (fl.category for fl in manifest.folder_locations if fl.is_primary),
        "",
    )
    for sec in artist.get("secondary_folders", []):
        ref = ReferenceManifest(
            artist_id=manifest.artist_id,
            primary_folder=primary_path,
            primary_category=primary_category,
            display_name=manifest.identity.display_name,
            generated_at=manifest.generated_at,
        )
        ref_path = os.path.join(sec["folder_path"], MANIFEST_FILENAME)
        _write_json(ref_path, ref.model_dump())
        written.append(ref_path)

    return written


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mark_most_recent_current(docs: list[DocumentEntry]) -> None:
    """Mark only the most-recent doc as current."""
    if len(docs) <= 1:
        return
    dated = sorted(docs, key=lambda d: d.date or "0000", reverse=True)
    for d in dated:
        d.is_current = False
    dated[0].is_current = True


def _unique_image_folders(image_paths: list[str]) -> list[str]:
    """Return unique parent directories containing images."""
    folders: set[str] = set()
    for p in image_paths:
        folders.add(os.path.dirname(p))
    return sorted(folders)


def _preserve_ai_enrichment(manifest_path: str, data: dict) -> None:
    """Carry forward ai_enrichment block from existing manifest."""
    if not os.path.isfile(manifest_path):
        return
    try:
        with open(manifest_path, encoding="utf-8") as fh:
            existing = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return

    ai = existing.get("ai_enrichment")
    if not ai:
        return

    data["ai_enrichment"] = ai

    # Re-apply website if enricher wrote one and new manifest lacks it
    ai_website = ai.get("website")
    if ai_website and not data.get("contact", {}).get("website"):
        data.setdefault("contact", {})["website"] = ai_website


def _write_json(path: str, data: dict) -> None:
    """Write data as indented JSON."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
