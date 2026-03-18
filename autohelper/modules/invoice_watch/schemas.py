"""Invoice watch Pydantic schemas."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class WatchEventType(str, Enum):
    """Types of filesystem events for invoices."""

    INVOICE_EXPORTED = "invoice_exported"
    BILL_RECEIVED = "bill_received"
    RECEIPT_RECEIVED = "receipt_received"
    FILE_MOVED = "file_moved"
    FILE_DELETED = "file_deleted"


class WatchedFolder(str, Enum):
    """Expected subdirectories per project."""

    INVOICES = "invoices"
    BILLS = "bills"
    RECEIPTS = "receipts"
    EXPORTS = "exports"


class WatchProjectCommand(BaseModel):
    """Command to start watching a project folder."""

    project_id: str
    root_path: str
    folders: list[str] = Field(default_factory=lambda: [f.value for f in WatchedFolder])


class UnwatchProjectCommand(BaseModel):
    """Command to stop watching a project folder."""

    project_id: str


class FileEvent(BaseModel):
    """A detected filesystem event."""

    event_type: WatchEventType
    project_id: str
    filename: str
    path: str
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    invoice_number: str | None = None
    suggested_vendor: str | None = None
    from_path: str | None = None  # For move events


class ValidateNumberRequest(BaseModel):
    """Request to validate an invoice number against disk."""

    number: str
    project_root: str


class ValidateNumberResponse(BaseModel):
    """Response from invoice number disk validation."""

    exists_on_disk: bool
    matching_files: list[str] = Field(default_factory=list)
