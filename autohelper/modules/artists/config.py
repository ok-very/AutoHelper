"""
Artist Records configuration — loaded from artist_lexicon.json at runtime.

All scanning constants (subfolder aliases, identity options, completeness weights,
folder fixes, multi-folder overrides, category profiles) live in the lexicon JSON
so they can be edited without code changes.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autohelper.shared.paths import data_dir

logger = logging.getLogger(__name__)

LEXICON_FILENAME = "artist_lexicon.json"
MANIFEST_FILENAME = "artist_manifest.json"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CategoryProfile:
    """Defines how a top-level category maps to artist folders."""

    key: str  # "indigenous", "public", "private", "corporate"
    rel_path: str  # relative to storage root
    layout: str  # "nation_based", "bucketed", "flat"
    label: str  # display name


@dataclass
class DomainConfig:
    """Per-domain scan settings (confidence, extra ignores, etc.)."""

    key: str
    confidence: float = 0.8
    extra_ignore_dirs: list[str] = field(default_factory=list)


@dataclass
class ArtistLexicon:
    """All scanning configuration, loaded from artist_lexicon.json."""

    version: str = "1.0"

    categories: list[CategoryProfile] = field(default_factory=list)
    subfolder_aliases: dict[str, str] = field(default_factory=dict)
    image_extensions: set[str] = field(default_factory=set)
    document_extensions: set[str] = field(default_factory=set)
    ignore_files: set[str] = field(default_factory=set)
    ignore_dirs: set[str] = field(default_factory=set)

    completeness_weights: dict[str, float] = field(default_factory=dict)
    completeness_gap_labels: dict[str, str] = field(default_factory=dict)

    identity_options: list[str] = field(default_factory=list)
    affiliation_types: list[str] = field(default_factory=list)
    location_types: list[str] = field(default_factory=list)
    name_types: list[str] = field(default_factory=list)
    career_stages: list[str] = field(default_factory=list)

    folder_name_fixes: dict[str, str] = field(default_factory=dict)
    multi_folder_artists: dict[str, dict] = field(default_factory=dict)
    collaborative_entities: dict[str, dict] = field(default_factory=dict)
    nested_artists: dict[str, dict] = field(default_factory=dict)

    # Per-domain scan config (confidence, extra ignores)
    domain_configs: dict[str, DomainConfig] = field(default_factory=dict)

    # Per-artist identity overrides: "category:nation:folder_name" -> {identities, affiliations, locations, pronouns}
    artist_identity_overrides: dict[str, dict] = field(default_factory=dict)

    # Regex patterns for folder names that are NOT artists (admin/org folders)
    non_artist_patterns: list[str] = field(default_factory=list)

    # Path to the ground-truth contacts CSV for artist validation / enrichment
    ground_truth_csv_path: str | None = None

    # Derived lookup: (category, folder_name) -> canonical_id
    multi_folder_lookup: dict[tuple[str, str], str] = field(
        default_factory=dict, repr=False
    )

    # Compiled regexes (not serialized)
    _non_artist_compiled: list[re.Pattern] = field(
        default_factory=list, repr=False
    )


# ---------------------------------------------------------------------------
# Built-in defaults
# ---------------------------------------------------------------------------

DEFAULT_CATEGORIES: list[CategoryProfile] = [
    CategoryProfile(
        "public",
        "1. PUBLIC ART/ARTIST INFORMATION/ARTIST Folders",
        "flat",
        "Public Art",
    ),
    CategoryProfile(
        "private", "2. PRIVATE ART/03 Artists", "bucketed", "Private Art"
    ),
    CategoryProfile(
        "corporate", "3. CORPORATE ART/Artists", "flat", "Corporate Art"
    ),
]

DEFAULT_SUBFOLDER_ALIASES: dict[str, str] = {
    "bio": "Bio",
    "bios": "Bio",
    "biography": "Bio",
    "cv": "CV",
    "cvs": "CV",
    "curriculum vitae": "CV",
    "image": "Images",
    "images": "Images",
    "tearsheet": "Tearsheets",
    "tearsheets": "Tearsheets",
    "eoi": "EOI",
    "eois": "EOI",
    "concept proposal": "Concept Proposals",
    "concept proposals": "Concept Proposals",
    "proposal": "Concept Proposals",
    "proposals": "Concept Proposals",
    "project list": "Project list",
    "project lists": "Project list",
    "projects": "Project list",
    # PRIVATE ART numbered subfolder convention
    "01 artist bio": "Bio",
    "02 works": "Images",
    "04 tearsheets": "Tearsheets",
}

DEFAULT_IMAGE_EXTENSIONS: set[str] = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
    ".avif", ".tiff", ".tif", ".heic", ".heif",
}

DEFAULT_DOCUMENT_EXTENSIONS: set[str] = {
    ".pdf", ".docx", ".doc", ".txt", ".rtf", ".pptx", ".ppt", ".indd",
}

DEFAULT_IGNORE_FILES: set[str] = {
    ".tonfotos.ini", ".ds_store", "thumbs.db", "desktop.ini",
    ".bridgesort", ".tonfotos",
}

DEFAULT_IGNORE_DIRS: set[str] = {"__pycache__", ".git", "node_modules", ".artcollector"}

DEFAULT_COMPLETENESS_WEIGHTS: dict[str, float] = {
    "has_bio": 0.15,
    "has_cv": 0.10,
    "has_tearsheet": 0.15,
    "has_contact_email": 0.20,
    "has_contact_phone": 0.10,
    "has_website": 0.05,
    "has_images": 0.15,
    "has_pronouns": 0.10,
}

DEFAULT_COMPLETENESS_GAP_LABELS: dict[str, str] = {
    "has_bio": "Missing bio",
    "has_cv": "Missing CV",
    "has_tearsheet": "Missing tearsheet",
    "has_contact_email": "No contact email",
    "has_contact_phone": "No contact phone",
    "has_website": "No website",
    "has_images": "No images",
    "has_pronouns": "No pronouns",
}

DEFAULT_IDENTITIES: list[str] = [
    # Gender & sexuality
    "queer", "gay", "lesbian", "bisexual", "trans", "non-binary", "two-spirit",
    # Race & ethnicity
    "Indigenous", "First Nations", "Métis", "Inuit", "Black", "African", "PoC",
    "South Asian", "East Asian", "Southeast Asian", "Middle Eastern",
    "Latin American", "Caribbean",
    # Migration & origin
    "immigrant", "migrant", "refugee", "diaspora", "settler",
    # Other
    "disability", "Deaf", "religious", "cultural legacy",
]

DEFAULT_AFFILIATION_TYPES: list[str] = [
    "nation", "collective", "duo_partner", "studio_assistant_of",
    "band", "organization",
]

DEFAULT_LOCATION_TYPES: list[str] = [
    "origin",   # where the artist is from / born
    "home",     # where they currently live/work
    "studio",   # dedicated studio address
]

DEFAULT_NAME_TYPES: list[str] = [
    "traditional",   # Indigenous traditional/ceremonial name
    "pseudonym",     # artist alias / pen name
    "studio",        # studio or practice name
    "trade",         # registered trade name / business name
]

DEFAULT_CAREER_STAGES: list[str] = [
    "emerging",      # early-career, fewer than ~10 years active
    "mid-career",    # established practice, growing recognition
    "established",   # significant body of work, widely recognised
]

DEFAULT_FOLDER_NAME_FIXES: dict[str, str] = {
    "Martinez. Mauricio": "Martinez, Mauricio",
    "Atkins. Phyllis": "Atkins, Phyllis",
}

DEFAULT_MULTI_FOLDER_ARTISTS: dict[str, dict] = {
    "yuxweluptun_lawrence_paul": {
        "primary": "indigenous",
        "review_note": "Folder spelling differs across nations",
        "folders": [
            {"category": "indigenous", "nation": "Cowichan", "name": "Yuxweluptun, Lawrence Paul"},
            {"category": "indigenous", "nation": "Syilx", "name": "Yuxwelupton, Lawrence Paul"},
        ],
    },
    "klatle_bhi": {
        "primary": "indigenous",
        "review_note": "Klatle-bhi appears under multiple nations",
        "folders": [
            {"category": "indigenous", "nation": "Kwakwaka\u2019wakw", "name": "Klatle-bhi"},
            {"category": "indigenous", "nation": "Squamish", "name": "Klatle-bhi"},
        ],
    },
    "braeg_jason": {
        "primary": "indigenous",
        "folders": [
            {"category": "indigenous", "nation": "Cree", "name": "Braeg, Jason"},
            {"category": "indigenous", "nation": "M\xe9tis", "name": "Braeg, Jason"},
        ],
    },
    "sound_michelle": {
        "primary": "indigenous",
        "folders": [
            {"category": "indigenous", "nation": "Cree", "name": "Sound, Michelle"},
            {"category": "indigenous", "nation": "M\xe9tis", "name": "Sound, Michelle"},
        ],
    },
    "yeomans_don": {
        "primary": "indigenous",
        "folders": [
            {"category": "indigenous", "nation": "Haida", "name": "Yeomans, Don"},
            {"category": "indigenous", "nation": "M\xe9tis", "name": "Yeomans, Don"},
        ],
    },
    "kukwits_gigaemi": {
        "primary": "indigenous",
        "folders": [
            {"category": "indigenous", "nation": "Coast Salish", "name": "Kukwits, Gigaemi"},
            {"category": "indigenous", "nation": "Kwakwaka\u2019wakw", "name": "Kukwits, Gigaemi"},
            {"category": "indigenous", "nation": "Squamish", "name": "Kukwits, Gigaemi"},
        ],
    },
}

DEFAULT_COLLABORATIVE_ENTITIES: dict[str, dict] = {
    "indigenous:Coast Salish:Brevner, Lauren & James Harry": {
        "display_name": "Lauren Brevner & James Harry",
        "members": ["Lauren Brevner", "James Harry"],
    },
    "indigenous:Kwantlen:Atkins, Drew and Phyllis": {
        "display_name": "Drew and Phyllis Atkins",
        "members": ["Drew Atkins", "Phyllis Atkins"],
    },
    "indigenous:Semiahmoo:Wells, Leslie and Leonard": {
        "display_name": "Leslie and Leonard Wells",
        "members": ["Leslie Wells", "Leonard Wells"],
    },
}

DEFAULT_NESTED_ARTISTS: dict[str, dict] = {
    "indigenous:Squamish:Xwalacktun": {
        "traditional_name": "Xwalacktun",
        "western_subfolder": "Harry, Rick",
        "western_first": "Rick",
        "western_last": "Harry",
        "review_note": "Xwalacktun (traditional name) = Rick Harry",
    },
}

# Regex patterns that match folder names which are NOT artists.
# Applied to the raw folder name before any name parsing.
DEFAULT_NON_ARTIST_PATTERNS: list[str] = [
    # Date-prefixed folders (submissions, batches)
    r"^\d{4}[_\-]\d{2}",
    # Admin prefix conventions
    r"^a_",
    # Administrative / organizational folder names
    r"(?i)^(artist\s*(roster|list)|artwork\s*information|available\s*works)$",
    r"(?i)^(cloud\s*details|information)$",
    r"(?i)^cover\s*letter",
    r"(?i)^(emails?|corres?pondence|corresp[oa]ndence)$",
    r"(?i)^(first\s*nations[_\s]various)",
    r"(?i)^(templates?|archive|backup|old|admin|misc|general)$",
    r"(?i)^(shortlist|longlist|jury|selection|budget)$",
    r"(?i)^(meeting\s*notes?|minutes|agenda|reports?|schedules?)$",
    r"(?i)^(contracts?|invoices?|receipts?|purchase\s*orders?)$",
    # Proposal/submission/list folders (not artist names)
    r"(?i)\bproposals?\b",
    r"(?i)\bsubmissions?\b",
    r"(?i)^project\s*list",
    r"(?i)\bEOI\b.*\b(submission|list)",
    # Project folders, cancelled/on-hold items
    r"(?i)\(cancelled\)",
    r"(?i)\bcancelled\s+project\b",
    r"(?i)\(on\s*hold\)",
    r"(?i)\bproject\s+with\b",
    # Browser "Save Page As" artifact folders (e.g. "ADAM PARKER SMITH_files")
    r"_files$",
    # Document/asset folders mistaken for artists
    r"(?i)^bio(\s+and\s+|\s*\+\s*|\s|$)",
    r"(?i)^cv(\s|$)",
    r"(?i)^info(\s|$)",
    # Company abbreviations / internal names
    r"(?i)^bfa$",
    # EOI folders (broader than just "EOI submission/list")
    r"(?i)\bEOI\b",
]

DEFAULT_DOMAIN_CONFIGS: dict[str, DomainConfig] = {
    "public":     DomainConfig(key="public",     confidence=0.85),
    "private":    DomainConfig(key="private",     confidence=0.7),
    "corporate":  DomainConfig(key="corporate",   confidence=0.6),
}

# Category priority for choosing the primary folder
CATEGORY_PRIORITY: list[str] = ["public", "private", "corporate"]


# ---------------------------------------------------------------------------
# Lexicon singleton
# ---------------------------------------------------------------------------

_lexicon: ArtistLexicon | None = None


def get_lexicon() -> ArtistLexicon:
    """Get the cached lexicon, loading from disk or defaults."""
    global _lexicon
    if _lexicon is None:
        _lexicon = load_lexicon()
    return _lexicon


def reset_lexicon() -> None:
    """Force reload on next access."""
    global _lexicon
    _lexicon = None


def get_lexicon_path() -> Path:
    """Path to the lexicon JSON file."""
    return data_dir() / LEXICON_FILENAME


def load_lexicon() -> ArtistLexicon:
    """Load lexicon from disk, falling back to built-in defaults.

    After loading, compares the serialized result against the raw disk JSON.
    If defaults filled in missing keys (new fields added in code), the file
    is auto-saved so it never stays stale.
    """
    path = get_lexicon_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            lex = _parse_lexicon(raw)
            _auto_heal(path, raw, lex)
            return lex
        except Exception:
            logger.warning("Failed to load %s, using defaults", path, exc_info=True)

    # Generate from defaults
    lex = _build_default_lexicon()
    try:
        save_lexicon(lex)
    except Exception:
        logger.warning("Failed to save default lexicon to disk", exc_info=True)
    return lex


def _auto_heal(path: Path, raw: dict[str, Any], lex: ArtistLexicon) -> None:
    """Re-save the lexicon if _parse_lexicon filled in missing keys or patterns."""
    dirty = False
    canonical = _serialize_lexicon(lex)

    # Detect new top-level keys
    added_keys = set(canonical.keys()) - set(raw.keys())
    if added_keys:
        logger.info("Lexicon auto-heal: new keys %s", added_keys)
        dirty = True

    # Merge new default non_artist_patterns into existing list
    saved_patterns = set(lex.non_artist_patterns)
    for pat in DEFAULT_NON_ARTIST_PATTERNS:
        if pat not in saved_patterns:
            lex.non_artist_patterns.append(pat)
            logger.info("Lexicon auto-heal: added non_artist_pattern %r", pat)
            dirty = True

    # Sync category layouts with defaults (fixes misconfigured layouts)
    default_cat_map = {c.key: c for c in DEFAULT_CATEGORIES}
    updated_cats = []
    removed_keys = set()
    for cat in lex.categories:
        default = default_cat_map.get(cat.key)
        if default is None:
            # Category removed from defaults — drop it
            logger.info("Lexicon auto-heal: removing obsolete category %r", cat.key)
            removed_keys.add(cat.key)
            dirty = True
            continue
        if cat.layout != default.layout:
            logger.info(
                "Lexicon auto-heal: category %r layout %r -> %r",
                cat.key, cat.layout, default.layout,
            )
            cat.layout = default.layout
            dirty = True
        if cat.rel_path != default.rel_path:
            logger.info(
                "Lexicon auto-heal: category %r rel_path %r -> %r",
                cat.key, cat.rel_path, default.rel_path,
            )
            cat.rel_path = default.rel_path
            dirty = True
        updated_cats.append(cat)
    # Add any new default categories not already present
    existing_keys = {c.key for c in updated_cats}
    for dc in DEFAULT_CATEGORIES:
        if dc.key not in existing_keys:
            logger.info("Lexicon auto-heal: adding new category %r", dc.key)
            updated_cats.append(dc)
            dirty = True
    if dirty:
        lex.categories = updated_cats

    if dirty:
        _compile_patterns(lex)
        try:
            save_lexicon(lex)
            logger.info("Lexicon auto-healed and saved to %s", path)
        except Exception:
            logger.warning("Auto-heal save failed for %s", path, exc_info=True)


def save_lexicon(lex: ArtistLexicon) -> None:
    """Write lexicon to disk as JSON."""
    path = get_lexicon_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _serialize_lexicon(lex)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _build_default_lexicon() -> ArtistLexicon:
    """Construct a lexicon from built-in defaults."""
    lex = ArtistLexicon(
        categories=list(DEFAULT_CATEGORIES),
        subfolder_aliases=dict(DEFAULT_SUBFOLDER_ALIASES),
        image_extensions=set(DEFAULT_IMAGE_EXTENSIONS),
        document_extensions=set(DEFAULT_DOCUMENT_EXTENSIONS),
        ignore_files=set(DEFAULT_IGNORE_FILES),
        ignore_dirs=set(DEFAULT_IGNORE_DIRS),
        completeness_weights=dict(DEFAULT_COMPLETENESS_WEIGHTS),
        completeness_gap_labels=dict(DEFAULT_COMPLETENESS_GAP_LABELS),
        identity_options=list(DEFAULT_IDENTITIES),
        affiliation_types=list(DEFAULT_AFFILIATION_TYPES),
        location_types=list(DEFAULT_LOCATION_TYPES),
        name_types=list(DEFAULT_NAME_TYPES),
        career_stages=list(DEFAULT_CAREER_STAGES),
        folder_name_fixes=dict(DEFAULT_FOLDER_NAME_FIXES),
        multi_folder_artists=dict(DEFAULT_MULTI_FOLDER_ARTISTS),
        collaborative_entities=dict(DEFAULT_COLLABORATIVE_ENTITIES),
        nested_artists=dict(DEFAULT_NESTED_ARTISTS),
        domain_configs=dict(DEFAULT_DOMAIN_CONFIGS),
        artist_identity_overrides={},
        non_artist_patterns=list(DEFAULT_NON_ARTIST_PATTERNS),
    )
    _rebuild_lookup(lex)
    _compile_patterns(lex)
    return lex


def _compile_patterns(lex: ArtistLexicon) -> None:
    """Compile non_artist_patterns into regex objects."""
    lex._non_artist_compiled = []
    for pat in lex.non_artist_patterns:
        try:
            lex._non_artist_compiled.append(re.compile(pat))
        except re.error:
            logger.warning("Invalid non_artist_pattern regex: %s", pat)


def is_artist_folder(folder_name: str) -> bool:
    """Return True if folder_name looks like a real artist, False if it matches
    a known non-artist pattern (admin/org folder)."""
    lex = get_lexicon()
    for rx in lex._non_artist_compiled:
        if rx.search(folder_name):
            return False
    return True


def _rebuild_lookup(lex: ArtistLexicon) -> None:
    """Build the multi_folder_lookup from multi_folder_artists."""
    lex.multi_folder_lookup = {}
    for canonical_id, cfg in lex.multi_folder_artists.items():
        for folder in cfg.get("folders", []):
            key = (folder.get("category", ""), folder.get("nation", ""), folder.get("name", ""))
            lex.multi_folder_lookup[key] = canonical_id


def _parse_lexicon(data: dict[str, Any]) -> ArtistLexicon:
    """Parse a JSON dict into an ArtistLexicon."""
    lex = ArtistLexicon(
        version=data.get("version", "1.0"),
        categories=[
            CategoryProfile(**c) for c in data.get("categories", [])
        ] or list(DEFAULT_CATEGORIES),
        subfolder_aliases=data.get("subfolder_aliases", dict(DEFAULT_SUBFOLDER_ALIASES)),
        image_extensions=set(data.get("image_extensions", DEFAULT_IMAGE_EXTENSIONS)),
        document_extensions=set(data.get("document_extensions", DEFAULT_DOCUMENT_EXTENSIONS)),
        ignore_files=set(data.get("ignore_files", DEFAULT_IGNORE_FILES)),
        ignore_dirs=set(data.get("ignore_dirs", DEFAULT_IGNORE_DIRS)),
        completeness_weights=data.get("completeness_weights", dict(DEFAULT_COMPLETENESS_WEIGHTS)),
        completeness_gap_labels=data.get("completeness_gap_labels", dict(DEFAULT_COMPLETENESS_GAP_LABELS)),
        # Fall back to old key name for one-time migration of pre-refactor lexicon files
        identity_options=data.get("identity_options") or data.get("identity_labels", list(DEFAULT_IDENTITIES)),
        affiliation_types=data.get("affiliation_types", list(DEFAULT_AFFILIATION_TYPES)),
        location_types=data.get("location_types", list(DEFAULT_LOCATION_TYPES)),
        name_types=data.get("name_types", list(DEFAULT_NAME_TYPES)),
        career_stages=data.get("career_stages", list(DEFAULT_CAREER_STAGES)),
        folder_name_fixes=data.get("folder_name_fixes", dict(DEFAULT_FOLDER_NAME_FIXES)),
        multi_folder_artists=data.get("multi_folder_artists", dict(DEFAULT_MULTI_FOLDER_ARTISTS)),
        collaborative_entities=data.get("collaborative_entities", dict(DEFAULT_COLLABORATIVE_ENTITIES)),
        nested_artists=data.get("nested_artists", dict(DEFAULT_NESTED_ARTISTS)),
        domain_configs={
            k: DomainConfig(**v) if isinstance(v, dict) else v
            for k, v in data.get("domain_configs", DEFAULT_DOMAIN_CONFIGS).items()
        },
        artist_identity_overrides=data.get("artist_identity_overrides", {}),
        non_artist_patterns=data.get("non_artist_patterns", list(DEFAULT_NON_ARTIST_PATTERNS)),
        ground_truth_csv_path=data.get("ground_truth_csv_path"),
    )
    _rebuild_lookup(lex)
    _compile_patterns(lex)
    return lex


def _serialize_lexicon(lex: ArtistLexicon) -> dict[str, Any]:
    """Serialize an ArtistLexicon to a JSON-friendly dict."""
    return {
        "version": lex.version,
        "categories": [
            {"key": c.key, "rel_path": c.rel_path, "layout": c.layout, "label": c.label}
            for c in lex.categories
        ],
        "subfolder_aliases": lex.subfolder_aliases,
        "image_extensions": sorted(lex.image_extensions),
        "document_extensions": sorted(lex.document_extensions),
        "ignore_files": sorted(lex.ignore_files),
        "ignore_dirs": sorted(lex.ignore_dirs),
        "completeness_weights": lex.completeness_weights,
        "completeness_gap_labels": lex.completeness_gap_labels,
        "identity_options": lex.identity_options,
        "affiliation_types": lex.affiliation_types,
        "location_types": lex.location_types,
        "name_types": lex.name_types,
        "career_stages": lex.career_stages,
        "folder_name_fixes": lex.folder_name_fixes,
        "multi_folder_artists": lex.multi_folder_artists,
        "collaborative_entities": lex.collaborative_entities,
        "nested_artists": lex.nested_artists,
        "domain_configs": {
            k: {"key": v.key, "confidence": v.confidence, "extra_ignore_dirs": v.extra_ignore_dirs}
            for k, v in lex.domain_configs.items()
        },
        "artist_identity_overrides": lex.artist_identity_overrides,
        "non_artist_patterns": lex.non_artist_patterns,
        "ground_truth_csv_path": lex.ground_truth_csv_path,
    }
