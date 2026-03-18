"""
Mail Service Module
Handles background polling of Outlook Inbox and ingestion of PST/OST files.
Note: Outlook integration requires Windows with pywin32 installed.
"""

import json
import os
import re
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from autohelper.config import get_settings
from autohelper.db import get_db
from autohelper.shared.logging import get_logger

logger = get_logger(__name__)

# Windows-specific imports for Outlook COM automation
# Guarded to allow module import on non-Windows platforms
from autohelper.shared.platform import can_use_outlook, platform_label

_HAS_WIN32 = False
pythoncom: Any = None
win32com_client: Any = None

if can_use_outlook():
    try:
        import pythoncom as _pythoncom
        import win32com.client as _win32com_client

        pythoncom = _pythoncom
        win32com_client = _win32com_client
        _HAS_WIN32 = True
    except ImportError:
        logger.warning("pywin32 not installed; Outlook integration unavailable")

# =============================================================================
# CONSTANTS & CONFIG
# =============================================================================

KNOWN_DEVELOPERS = [
    "Qualex",
    "Anthem",
    "PCI",
    "Holborn",
    "Intracorp",
    "Beedie",
    "Polygon",
    "Avisina",
    "Peterson",
    "Aryze",
    "Onni",
    "Edgar",
    "Williams",
    "Greystar",
    "PC Urban",
    "Aragon",
    "Dayhu",
    "Bosa",
    "Dawson+Sawyer",
    "Vanprop",
    "Frame",
    "Placemaker",
    "QuadReal",
    "CF",
    "Intracrop",
]

ACTION_PATTERNS = {
    "Invoice": ["invoice", "payment", "billing", "INV-"],
    "Contract": ["contract", "agreement", "execution", "signing"],
    "Meeting": ["meeting", "schedule", "availability", "calendar", "call"],
    "Approval": ["approve", "approval", "sign off", "review and approve"],
    "Delivery": ["attached", "please find", "here is", "sending you"],
    "Request": ["please send", "can you", "requesting", "need from you"],
    "Update": ["update", "status", "progress", "fyi"],
    "FollowUp": ["following up", "reminder", "checking in"],
}

URGENCY_KEYWORDS = ["urgent", "asap", "deadline", "immediately", "critical", "time-sensitive"]
VIP_DOMAINS: list[str] = []  # Configurable later

# =============================================================================
# HELPER FUNCTIONS (Pure Logic)
# =============================================================================


def clean_subject(subject: str) -> str:
    """Remove RE:, FW:, [EXT], etc. from subject line."""
    prefixes = ["RE: ", "Re: ", "FW: ", "Fw: ", "[EXT] ", "EXTERNAL-", "[EXTERNAL]", "EXTERNAL: "]
    cleaned = subject
    for prefix in prefixes:
        cleaned = cleaned.replace(prefix, "")
    return cleaned.strip()


def extract_project_info(subject: str) -> tuple[str, str, str]:
    """
    Extract developer, project name, and topic from subject.
    Pattern: "Developer - Project - Topic"
    Returns: (developer, project_name, full_project_id)

    Uses ContextService for dynamic developer list if available,
    otherwise falls back to KNOWN_DEVELOPERS static list.
    """
    cleaned = clean_subject(subject)

    if " - " not in cleaned:
        return "", "", "_Uncategorized"

    parts = [p.strip() for p in cleaned.split(" - ")]

    if len(parts) >= 2:
        developer = parts[0]
        project = parts[1]

        # Try to get developers from ContextService
        known_developers = KNOWN_DEVELOPERS  # Default fallback
        try:
            from autohelper.modules.context.service import get_context_service

            ctx = get_context_service()
            dynamic_developers = ctx.get_developers()
            if dynamic_developers:
                known_developers = dynamic_developers
        except Exception:
            pass  # Use fallback

        # Validate developer is known
        developer_matched = any(dev.lower() in developer.lower() for dev in known_developers)

        if developer_matched:
            full_project_id = f"{developer} - {project}"
            return developer, project, full_project_id

    return "", "", "_Uncategorized"


def make_safe_filename(text: str, max_length: int = 50) -> str:
    """Convert text to a safe filename."""
    safe = re.sub(r'[\\/:*?"<>|]', "-", text)
    safe = re.sub(r"-+", "-", safe)
    return safe[:max_length].strip("-")


# =============================================================================
# SERVICE
# =============================================================================


class MailService:
    _instance: "MailService | None" = None
    _lock = threading.Lock()
    initialized: bool
    running: bool
    thread: threading.Thread | None

    def __new__(cls) -> "MailService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self.initialized:
            return

        self.settings = get_settings()
        self.running = False
        self.thread = None
        self.stop_event = threading.Event()
        self.initialized = True

    def start(self) -> None:
        """Start the background polling thread if enabled."""
        if not _HAS_WIN32:
            logger.info(
                "Mail Service: Skipped — requires Windows with Outlook (running on %s)",
                platform_label(),
            )
            return

        if not self.settings.mail_enabled:
            logger.info("Mail Service: Disabled in settings")
            return

        with self._lock:
            if self.running:
                return

            logger.info("Mail Service: Starting background polling...")
            self.stop_event.clear()
            self.thread = threading.Thread(target=self._poll_loop, daemon=True)
            self.thread.start()
            self.running = True

    def stop(self) -> None:
        """Stop the background polling thread."""
        with self._lock:
            if not self.running:
                return

            logger.info("Mail Service: Stopping...")
            self.running = False
            self.stop_event.set()
            thread = self.thread
            self.thread = None

        # Join outside lock to avoid deadlock
        if thread:
            thread.join(timeout=5)
        logger.info("Mail Service: Stopped")

    def _poll_loop(self) -> None:
        """Main polling loop running in background thread."""
        pythoncom.CoInitialize()  # Initialize COM for this thread

        try:
            while not self.stop_event.is_set():
                try:
                    self._check_inbox()
                except Exception as e:
                    logger.error(f"Mail Service Error: {e}")

                # Sleep in chunks to allow responsive stop
                for _ in range(self.settings.mail_poll_interval):
                    if self.stop_event.is_set():
                        break
                    time.sleep(1)

        finally:
            pythoncom.CoUninitialize()

    def _get_outlook(self) -> Any:
        """Get Outlook Application object securely."""
        if not _HAS_WIN32 or win32com_client is None:
            return None
        try:
            return win32com_client.Dispatch("Outlook.Application")
        except Exception:
            return None

    def _check_inbox(self) -> None:
        """Check Inbox for new emails in the last interval."""
        outlook = self._get_outlook()
        if not outlook:
            return

        namespace = outlook.GetNamespace("MAPI")
        inbox = namespace.GetDefaultFolder(6)  # 6 = Inbox

        # Look back slightly more than interval to ensure coverage
        seconds_back = self.settings.mail_poll_interval + 10
        cutoff = datetime.now() - timedelta(seconds=seconds_back)

        # Iterate (Optimize with restricted search in future if volume is high)
        # For now, iterating recent items is okay if inbox isn't huge,
        # but better to use Restrict or just check last N items if possible.
        # We'll trust the previous logic's approach but add a timestamp check.

        # Sort items? Default order is usually reliable but not guaranteed.
        # Let's iterate backwards or use Restrict for better perf

        items = inbox.Items
        items.Sort("[ReceivedTime]", True)  # Descending

        count = 0
        for item in items:
            # Stop if we went past the cutoff
            try:
                if not hasattr(item, "ReceivedTime"):
                    continue

                received = item.ReceivedTime
                # Pywin32 time conversion - skip items without valid timestamps
                if hasattr(received, "timestamp"):
                    dt = datetime.fromtimestamp(received.timestamp())
                else:
                    # Skip items without parseable timestamp to avoid reprocessing
                    subj = getattr(item, "Subject", "?")
                    logger.debug(f"Skipping item without valid timestamp: {subj}")
                    continue

                if dt < cutoff:
                    break  # We are done

                # Process
                self._process_email_item(item)
                count += 1

                if count > 50:  # Safety guard
                    break

            except Exception as e:
                logger.warning(f"Skipping item due to error: {e}")
                continue

    def _process_email_item(self, item: Any) -> bool:
        """Process a single email item."""
        import hashlib

        try:
            subject = getattr(item, "Subject", "(no subject)")
            sender = getattr(item, "SenderEmailAddress", "")

            # Get received time first (needed for fallback entry_id generation)
            # Use getattr to safely handle non-mail items that lack ReceivedTime
            received_time = getattr(item, "ReceivedTime", None)
            if received_time is not None and hasattr(received_time, "timestamp"):
                received_dt = datetime.fromtimestamp(received_time.timestamp())
            else:
                # Use sentinel date for items without timestamps to ensure deterministic entry_id
                received_dt = datetime(1970, 1, 1)

            # 1. Get or generate entry_id BEFORE duplicate check
            entry_id = getattr(item, "EntryID", "")
            if not entry_id:
                # Generate deterministic fallback ID from content
                content_key = f"{sender}|{subject}|{received_dt.isoformat()}"
                entry_id = f"gen_{hashlib.sha256(content_key.encode()).hexdigest()[:16]}"

            # 2. Check if we already processed it (DB check)
            if self._is_processed(entry_id):
                return False

            # 3. Extract Data
            dev, proj, proj_id = extract_project_info(subject)

            # 4. Save to Disk (OneDrive)
            output_base = self.settings.mail_output_path

            date_str = received_dt.strftime("%Y-%m-%d")
            safe_sub = make_safe_filename(clean_subject(subject))
            folder_name = f"{date_str}_{safe_sub}"

            project_folder = output_base / make_safe_filename(proj_id, 100)
            email_folder = project_folder / folder_name

            if email_folder.exists():
                # Already on disk, maybe from another run
                return False

            email_folder.mkdir(parents=True, exist_ok=True)

            # Save body
            body = getattr(item, "Body", "")
            with open(email_folder / "body.txt", "w", encoding="utf-8") as f:
                f.write(body)

            # Attachments - guard against items without Attachments collection
            attachments = getattr(item, "Attachments", None)
            if attachments is not None and attachments.Count > 0:
                att_folder = email_folder / "attachments"
                att_folder.mkdir(exist_ok=True)
                for i in range(attachments.Count):
                    att = attachments.Item(i + 1)

                    # Sanitize filename and handle collisions
                    raw_name = getattr(att, "FileName", "") or "attachment"
                    safe_name = make_safe_filename(raw_name, max_length=100)

                    base, ext = os.path.splitext(safe_name)
                    candidate = att_folder / safe_name
                    index = 1
                    while candidate.exists():
                        candidate = att_folder / f"{base}_{index}{ext}"
                        index += 1

                    att.SaveAsFile(str(candidate))

            # 5. Save to DB (Transient)
            self._save_transient_record(item, proj_id, received_dt, entry_id)

            return True

        except Exception as e:
            logger.error(f"Failed to process email: {e}")
            return False

    def _is_processed(self, entry_id: str) -> bool:
        """Check if email ID is already in our DB."""
        if not entry_id:
            # Empty entry_id cannot be reliably tracked - treat as unprocessed
            # but caller should generate a fallback ID
            return False
        db = get_db()
        row = db.execute("SELECT 1 FROM transient_emails WHERE id = ?", (entry_id,)).fetchone()
        return row is not None

    def _save_transient_record(
        self, item: Any, project_id: str, received_dt: datetime, entry_id: str
    ) -> None:
        """Save email metadata to SQLite."""
        db = get_db()

        subject = getattr(item, "Subject", "")
        sender = getattr(item, "SenderEmailAddress", "")
        body = getattr(item, "Body", "")[:500]  # Preview
        body_html = getattr(item, "HTMLBody", None)

        metadata = {
            "importance": getattr(item, "Importance", 1),
            "dev": extract_project_info(subject)[0],
        }

        db.execute(
            """
            INSERT OR IGNORE INTO transient_emails
                (id, subject, sender, received_at, project_id, body_preview, body_html, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (entry_id, subject, sender, received_dt, project_id, body, body_html, json.dumps(metadata)),
        )
        db.commit()

    # =========================================================================
    # PST INGESTION
    # =========================================================================

    def ingest_pst(self, pst_path: str) -> dict[str, Any]:
        """
        Ingest a PST file, extract emails, and cleanup.
        Ran in a separate thread usually, or blocking if called directly.

        Security: Only files under mail_ingest_path with .pst/.ost extension are allowed.
        """
        if not _HAS_WIN32:
            return {"success": False, "error": "Outlook integration unavailable (Windows only)"}

        path = Path(pst_path).resolve()

        # Security: Validate file extension
        if path.suffix.lower() not in (".pst", ".ost"):
            return {
                "success": False,
                "error": "Invalid file type. Only .pst and .ost files are allowed.",
            }

        # Security: Validate path is under configured ingest directory
        ingest_base = self.settings.mail_ingest_path.resolve()
        try:
            path.relative_to(ingest_base)
        except ValueError:
            return {"success": False, "error": f"File must be located under {ingest_base}"}

        if not path.exists():
            return {"success": False, "error": "File not found"}

        logger.info(f"Ingesting PST: {path}")

        # Record Ingestion Start
        db = get_db()
        cur = db.execute(
            "INSERT INTO mail_ingestion_log (source_path, status) VALUES (?, ?)",
            (str(path), "processing"),
        )
        ingest_id = cur.lastrowid
        db.commit()

        processed_count = 0

        try:
            # Need COM thread initialization if running in worker
            pythoncom.CoInitialize()

            outlook = self._get_outlook()
            if not outlook:
                raise Exception("Outlook not available")

            namespace = outlook.GetNamespace("MAPI")

            # Add Store
            namespace.AddStore(str(path))

            # Find the store folder
            pst_folder = None
            for f in namespace.Folders:
                # Basic matching
                if path.stem.lower() in f.Name.lower():
                    pst_folder = f
                    break

            if not pst_folder:
                # Try last folder
                pst_folder = namespace.Folders.Item(namespace.Folders.Count)

            # Process recursively
            processed_count = self._process_folder_recursive(pst_folder, ingest_id)

            # Remove Store
            # Standard Outlook way to close PST: RemoveStore(folder)
            namespace.RemoveStore(pst_folder)

            # Cleanup File
            # WARNING: Only delete if successful? User request said 'safely deleted'.
            # We will delete if no critical errors.
            try:
                os.remove(path)
            except Exception as e:
                logger.warning(f"Could not delete PST file: {e}")

            # Update Log
            db.execute(
                "UPDATE mail_ingestion_log SET status = ?, email_count = ? WHERE id = ?",
                ("completed", processed_count, ingest_id),
            )
            db.commit()

            return {"success": True, "count": processed_count}

        except Exception as e:
            db.execute(
                "UPDATE mail_ingestion_log SET status = ?, error_message = ? WHERE id = ?",
                ("failed", str(e), ingest_id),
            )
            db.commit()
            return {"success": False, "error": str(e)}
        finally:
            pythoncom.CoUninitialize()

    def _process_folder_recursive(self, folder: Any, ingest_id: int | None) -> int:
        count = 0
        folder_name = getattr(folder, "Name", "<unknown>")

        # Items
        try:
            for item in folder.Items:
                try:
                    # olMail class, and successfully processed
                    if getattr(item, "Class", 0) == 43 and self._process_ingested_item(
                        item, ingest_id
                    ):
                        count += 1
                except Exception as item_err:
                    logger.warning(f"Error processing item in folder '{folder_name}': {item_err}")
                    continue
        except Exception as items_err:
            logger.error(f"Error iterating items in folder '{folder_name}': {items_err}")

        # Subfolders
        try:
            for sub in folder.Folders:
                try:
                    count += self._process_folder_recursive(sub, ingest_id)
                except Exception as sub_err:
                    sub_name = getattr(sub, "Name", "<unknown>")
                    logger.error(f"Error processing subfolder '{sub_name}': {sub_err}")
                    continue
        except Exception as folders_err:
            logger.error(f"Error iterating subfolders in '{folder_name}': {folders_err}")

        return count

    def _process_ingested_item(self, item: Any, ingest_id: int | None) -> bool:
        """Process item from PST."""
        import hashlib

        subject = getattr(item, "Subject", "(no subject)")
        sender = getattr(item, "SenderEmailAddress", "")

        received_time = getattr(item, "ReceivedTime", None)
        if received_time and hasattr(received_time, "timestamp"):
            received_dt = datetime.fromtimestamp(received_time.timestamp())
        else:
            # Use a sentinel date for items without timestamps
            received_dt = datetime(1970, 1, 1)

        # Get or generate entry_id
        entry_id = getattr(item, "EntryID", "")
        if not entry_id:
            # Generate deterministic ID from content
            content_key = f"{sender}|{subject}|{received_dt.isoformat()}"
            entry_id = f"pst_{hashlib.sha256(content_key.encode()).hexdigest()[:16]}"

        # Check DB for duplicates
        if self._is_processed(entry_id):
            return False

        dev, proj, proj_id = extract_project_info(subject)

        # Save to Transient DB with ingest_id
        db = get_db()
        body = getattr(item, "Body", "")[:500]

        metadata = {
            "source": "pst",
            "folder": str(item.Parent.Name) if hasattr(item, "Parent") else "",
        }

        db.execute(
            """
            INSERT INTO transient_emails
                (id, subject, sender, received_at, project_id, body_preview,
                 metadata, ingestion_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_id,
                subject,
                sender,
                received_dt,
                proj_id,
                body,
                json.dumps(metadata),
                ingest_id,
            ),
        )
        db.commit()

        return True
