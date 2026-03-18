"""Contact Sync data types."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ContactRecord:
    """A single contact parsed from the master CSV."""

    email_primary: str
    full_name: str = ""
    first_name: str = ""
    last_name: str = ""
    company: str = ""
    job_title: str = ""
    phone_business: str = ""
    phone_mobile: str = ""
    street_address: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    country: str = ""
    category_canonical: str = ""

    def row_hash(self) -> str:
        """Compute a hash of all fields for change detection."""
        import hashlib

        parts = [
            self.email_primary, self.full_name, self.first_name, self.last_name,
            self.company, self.job_title, self.phone_business, self.phone_mobile,
            self.street_address, self.city, self.state, self.postal_code,
            self.country, self.category_canonical,
        ]
        blob = "|".join(parts).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()[:16]


@dataclass
class SyncResult:
    """Result of a contact sync run."""

    started_at: datetime
    completed_at: datetime | None = None
    status: str = "running"  # "running", "completed", "failed", "skipped", "dry_run"
    created: int = 0
    updated: int = 0
    deleted: int = 0
    unchanged: int = 0
    errors: list[str] = field(default_factory=list)
    dry_run: bool = False
    file_hash: str = ""
    csv_row_count: int = 0
    duration_ms: int = 0
