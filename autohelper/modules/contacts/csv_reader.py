"""CSV reader for master contacts file.

Handles:
- UTF-8 with BOM (utf-8-sig) from Excel exports
- Field normalization and whitespace stripping
- Deduplication by email_primary (last row wins)
"""

import csv
import hashlib
import logging
from pathlib import Path

from .types import ContactRecord

logger = logging.getLogger(__name__)

# Map CSV column headers (case-insensitive) to ContactRecord fields.
# Supports multiple common header variants.
HEADER_MAP: dict[str, str] = {
    "email": "email_primary",
    "email_primary": "email_primary",
    "emailaddress": "email_primary",
    "email_address": "email_primary",
    "e-mail": "email_primary",
    "full_name": "full_name",
    "fullname": "full_name",
    "name": "full_name",
    "displayname": "full_name",
    "display_name": "full_name",
    "first_name": "first_name",
    "firstname": "first_name",
    "given_name": "first_name",
    "givenname": "first_name",
    "last_name": "last_name",
    "lastname": "last_name",
    "surname": "last_name",
    "family_name": "last_name",
    "company": "company",
    "organization": "company",
    "companyname": "company",
    "company_name": "company",
    "job_title": "job_title",
    "jobtitle": "job_title",
    "title": "job_title",
    "phone_business": "phone_business",
    "businessphone": "phone_business",
    "business_phone": "phone_business",
    "phone": "phone_business",
    "workphone": "phone_business",
    "work_phone": "phone_business",
    "phone_mobile": "phone_mobile",
    "mobilephone": "phone_mobile",
    "mobile_phone": "phone_mobile",
    "mobile": "phone_mobile",
    "cellphone": "phone_mobile",
    "cell_phone": "phone_mobile",
    "street_address": "street_address",
    "streetaddress": "street_address",
    "address": "street_address",
    "street": "street_address",
    "city": "city",
    "state": "state",
    "stateorprovince": "state",
    "state_or_province": "state",
    "province": "state",
    "postal_code": "postal_code",
    "postalcode": "postal_code",
    "zip": "postal_code",
    "zipcode": "postal_code",
    "zip_code": "postal_code",
    "country": "country",
    "countryorregion": "country",
    "country_or_region": "country",
    "category_canonical": "category_canonical",
    "category": "category_canonical",
    "department": "category_canonical",
}


def file_hash(path: Path) -> str:
    """Compute SHA-256 hash of the file contents (first 16 hex chars)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def read_contacts_csv(path: Path) -> list[ContactRecord]:
    """
    Parse the master contacts CSV and return deduplicated ContactRecord list.

    Deduplicates by email_primary (case-insensitive, last row wins).
    Skips rows with no email_primary.
    """
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")

    contacts: dict[str, ContactRecord] = {}

    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header row: {path}")

        # Build column mapping for this file
        col_map: dict[str, str] = {}
        for header in reader.fieldnames:
            normalized = header.strip().lower().replace(" ", "_").replace("-", "_")
            if normalized in HEADER_MAP:
                col_map[header] = HEADER_MAP[normalized]

        if "email_primary" not in col_map.values():
            raise ValueError(
                f"CSV missing email column. Headers found: {reader.fieldnames}"
            )

        for row_num, row in enumerate(reader, start=2):
            kwargs: dict[str, str] = {}
            for csv_col, field_name in col_map.items():
                value = (row.get(csv_col) or "").strip()
                kwargs[field_name] = value

            email = kwargs.get("email_primary", "").lower()
            if not email:
                continue

            kwargs["email_primary"] = email

            # Auto-derive full_name if missing
            if not kwargs.get("full_name"):
                first = kwargs.get("first_name", "")
                last = kwargs.get("last_name", "")
                kwargs["full_name"] = f"{first} {last}".strip()

            contacts[email] = ContactRecord(**kwargs)

    logger.info("Parsed %d contacts from %s", len(contacts), path)
    return list(contacts.values())
