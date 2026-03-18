"""
Ground truth integration: loads the compiled contacts CSV and provides
fuzzy name matching for artist validation and contact enrichment.

Ported from BFA-artist-lists/scripts/excel_parser.py with adaptations
for the Categories column and domain validation.
"""
from __future__ import annotations

import csv
import logging
import re
from typing import Any

from .utils import normalize_name

logger = logging.getLogger(__name__)

# Categories in the CSV that indicate an artist (lowercased, dash-normalised)
ARTIST_CATEGORIES: set[str] = {
    "artists - general",
    "artists - public art",
    "indigenous artists / advisors",
    "indigenous artists/advisors",
}

# Map CSV categories to scanner domain keys
CATEGORY_TO_DOMAIN: dict[str, str] = {
    "artists - general": "public",
    "artists - public art": "public",
    "indigenous artists / advisors": "indigenous",
    "indigenous artists/advisors": "indigenous",
}


class GroundTruthIndex:
    """In-memory index of ground truth contacts for fast lookup."""

    def __init__(self) -> None:
        self._by_name: dict[tuple[str, str], dict[str, Any]] = {}
        self._artist_records: list[dict[str, Any]] = []

    @classmethod
    def from_csv(cls, csv_path: str) -> GroundTruthIndex:
        """Load from the compiled contacts CSV."""
        idx = cls()
        try:
            with open(csv_path, encoding="utf-8-sig", errors="replace", newline="") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    record = cls._parse_row(row)
                    if not record:
                        continue

                    key = (record["norm_last"], record["norm_first"])
                    if key not in idx._by_name:
                        idx._by_name[key] = record
                    else:
                        _merge_into(idx._by_name[key], record)

                    if record["is_artist"]:
                        idx._artist_records.append(record)

        except OSError as e:
            logger.warning("Could not load ground truth CSV: %s", e)

        logger.info(
            "Ground truth: %d contacts loaded, %d tagged as artists",
            len(idx._by_name), len(idx._artist_records),
        )
        return idx

    @staticmethod
    def _parse_row(row: dict[str, str]) -> dict[str, Any] | None:
        first = (row.get("First Name") or "").strip()
        last = (row.get("Last Name") or "").strip()
        if not first and not last:
            return None

        # Parse semicolon-delimited categories, fix mojibake em-dashes
        raw_cats = (row.get("Categories") or "").strip()
        categories = [_fix_mojibake(c.strip().lower()) for c in raw_cats.split(";") if c.strip()]

        is_artist = any(c in ARTIST_CATEGORIES for c in categories)
        artist_domains: set[str] = set()
        for c in categories:
            if c in CATEGORY_TO_DOMAIN:
                artist_domains.add(CATEGORY_TO_DOMAIN[c])

        email = _clean_email(
            row.get("E-mail Address", "").strip()
            or row.get("E-mail 2 Address", "").strip()
        )
        phone = _clean_phone(
            row.get("Business Phone", "").strip()
            or row.get("Mobile Phone", "").strip()
            or row.get("Home Phone", "").strip()
        )

        return {
            "first_name": first,
            "last_name": last,
            "norm_first": normalize_name(first),
            "norm_last": normalize_name(last),
            "company": (row.get("Company") or "").strip() or None,
            "job_title": (row.get("Job Title") or "").strip() or None,
            "email": email,
            "phone": phone,
            "categories": categories,
            "is_artist": is_artist,
            "artist_domains": artist_domains,
            "notes": (row.get("Notes") or "").strip() or None,
        }

    def find_contact(
        self,
        last_name: str | None,
        first_name: str | None,
        display_name: str | None = None,
    ) -> dict[str, Any] | None:
        """
        BFA-style fuzzy lookup: exact -> last-name + first-4-chars guard -> display name.
        """
        if last_name:
            nl = normalize_name(last_name)
            nf = normalize_name(first_name or "")
            key = (nl, nf)
            if key in self._by_name:
                return self._by_name[key]

            # Last-name-only fallback with first-4-chars guard
            for (kl, kf), rec in self._by_name.items():
                if kl == nl:
                    prefix = min(4, len(nf), len(kf))
                    if not nf or not kf:
                        if not nf and not kf:
                            return rec
                    elif prefix >= 2 and nf[:prefix] == kf[:prefix]:
                        return rec

        if display_name:
            nd = normalize_name(display_name)
            for (kl, kf), rec in self._by_name.items():
                full_key = f"{kl}_{kf}" if kf else kl
                if full_key == nd or nd == f"{kf}_{kl}":
                    return rec

        return None

    def validate_domain(
        self, record: dict[str, Any], expected_domain: str
    ) -> list[str]:
        """Check artist record's domain placement against ground truth."""
        match = self.find_contact(
            record.get("last_name"), record.get("first_name"), record.get("display_name")
        )
        if not match:
            return ["no_ground_truth_match"]

        flags = ["ground_truth_match"]
        if not match["is_artist"]:
            flags.append("ground_truth_not_artist")
        if match["artist_domains"] and expected_domain not in match["artist_domains"]:
            flags.append(
                f"ground_truth_domain_mismatch:expected={expected_domain},"
                f"found={','.join(sorted(match['artist_domains']))}"
            )
        return flags

    @property
    def artist_count(self) -> int:
        return len(self._artist_records)

    @property
    def total_count(self) -> int:
        return len(self._by_name)


def _fix_mojibake(s: str) -> str:
    """Fix common UTF-8 mojibake: replace em-dash variants with plain dash."""
    s = s.replace("\u00e2\u20ac\u201c", " - ")
    s = s.replace("\u00e2\u20ac\u201d", " - ")
    s = s.replace("\u2014", " - ")
    s = s.replace("\u2013", " - ")
    return s


def _clean_email(raw: str | None) -> str | None:
    if not raw:
        return None
    raw = raw.strip().lower()
    if "@" in raw and "." in raw.split("@")[-1]:
        return raw
    return None


def _clean_phone(raw: str | None) -> str | None:
    if not raw:
        return None
    s = str(raw).strip()
    s = re.sub(r"[^\d\s\+\(\)\-\.]", "", s).strip()
    return s if s else None


def _merge_into(target: dict, source: dict) -> None:
    """Fill in missing fields in target from source."""
    for k, v in source.items():
        if k in ("norm_first", "norm_last"):
            continue
        if not target.get(k) and v:
            target[k] = v
