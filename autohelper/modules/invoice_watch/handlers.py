"""Filesystem event handlers for invoice watching."""

import logging
import re
from pathlib import Path
from typing import Union

from watchdog.events import (
    DirCreatedEvent,
    DirDeletedEvent,
    DirMovedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileMovedEvent,
    FileSystemEventHandler,
)

from .schemas import FileEvent, WatchEventType, WatchedFolder

logger = logging.getLogger(__name__)

# Common invoice filename patterns
INVOICE_PATTERN = re.compile(
    r"(?:INV|inv)[-_]?\d{4}[-_]\d{3,6}",
    re.IGNORECASE,
)


def extract_invoice_number(filename: str) -> str | None:
    """Extract invoice number from filename."""
    match = INVOICE_PATTERN.search(filename)
    if match:
        return match.group(0).upper().replace("_", "-")
    return None


def classify_folder(path: Path, project_root: Path) -> WatchedFolder | None:
    """Determine which watched folder a file belongs to."""
    try:
        relative = path.relative_to(project_root)
    except ValueError:
        return None

    parts = relative.parts
    if not parts:
        return None

    first_dir = parts[0].lower()
    for folder in WatchedFolder:
        if first_dir == folder.value:
            return folder
    return None


class InvoiceWatchHandler(FileSystemEventHandler):
    """Handles filesystem events for invoice watching."""

    def __init__(
        self,
        project_id: str,
        project_root: Path,
        event_queue: list[FileEvent],
    ) -> None:
        super().__init__()
        self.project_id = project_id
        self.project_root = project_root
        self.event_queue = event_queue

    def on_created(self, event: Union[FileCreatedEvent, DirCreatedEvent]) -> None:
        if event.is_directory:
            return

        path = Path(str(event.src_path))
        folder = classify_folder(path, self.project_root)
        if folder is None:
            return

        file_event = self._build_event(path, folder)
        if file_event:
            self.event_queue.append(file_event)
            logger.info(
                "Invoice watch: %s detected %s in %s",
                file_event.event_type.value,
                path.name,
                folder.value,
            )

    def on_moved(self, event: Union[FileMovedEvent, DirMovedEvent]) -> None:
        if event.is_directory:
            return

        src_path = Path(str(event.src_path))
        dest_path = Path(str(event.dest_path))

        src_folder = classify_folder(src_path, self.project_root)
        dest_folder = classify_folder(dest_path, self.project_root)

        # Only alert if moved out of expected structure
        if src_folder and not dest_folder:
            file_event = FileEvent(
                event_type=WatchEventType.FILE_MOVED,
                project_id=self.project_id,
                filename=dest_path.name,
                path=str(dest_path),
                from_path=str(src_path),
                invoice_number=extract_invoice_number(src_path.name),
            )
            self.event_queue.append(file_event)
            logger.warning(
                "Invoice watch: file moved outside expected structure: %s -> %s",
                src_path,
                dest_path,
            )

    def on_deleted(self, event: Union[FileDeletedEvent, DirDeletedEvent]) -> None:
        if event.is_directory:
            return

        path = Path(str(event.src_path))
        folder = classify_folder(path, self.project_root)
        if folder is None:
            return

        file_event = FileEvent(
            event_type=WatchEventType.FILE_DELETED,
            project_id=self.project_id,
            filename=path.name,
            path=str(path),
            invoice_number=extract_invoice_number(path.name),
        )
        self.event_queue.append(file_event)

    def _build_event(self, path: Path, folder: WatchedFolder) -> FileEvent | None:
        """Build appropriate event based on folder type."""
        if folder == WatchedFolder.INVOICES:
            return FileEvent(
                event_type=WatchEventType.INVOICE_EXPORTED,
                project_id=self.project_id,
                filename=path.name,
                path=str(path),
                invoice_number=extract_invoice_number(path.name),
            )
        elif folder == WatchedFolder.BILLS:
            return FileEvent(
                event_type=WatchEventType.BILL_RECEIVED,
                project_id=self.project_id,
                filename=path.name,
                path=str(path),
                suggested_vendor=self._guess_vendor(path.name),
            )
        elif folder == WatchedFolder.RECEIPTS:
            return FileEvent(
                event_type=WatchEventType.RECEIPT_RECEIVED,
                project_id=self.project_id,
                filename=path.name,
                path=str(path),
            )
        return None

    @staticmethod
    def _guess_vendor(filename: str) -> str | None:
        """Attempt to extract vendor name from filename."""
        # Remove extension and common prefixes
        name = Path(filename).stem
        # Remove date-like patterns
        name = re.sub(r"\d{4}[-_]\d{2}[-_]\d{2}", "", name)
        name = re.sub(r"\d{6,8}", "", name)
        # Clean up
        name = name.strip("-_ ")
        return name if name else None
