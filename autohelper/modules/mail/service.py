"""
Mail Service Module
Handles background polling of Outlook Inbox and ingestion of PST/OST files.
Note: Outlook integration requires Windows with pywin32 installed.
"""

import os
import sys
import time
import json
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple, Any
import re

from autohelper.config import get_settings
from autohelper.db import get_db
from autohelper.shared.logging import get_logger

logger = get_logger(__name__)

# Windows-specific imports for Outlook COM automation
# Guarded to allow module import on non-Windows platforms
_HAS_WIN32 = False
pythoncom: Any = None
win32com_client: Any = None

if sys.platform == "win32":
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
    "Qualex", "Anthem", "PCI", "Holborn", "Intracorp", "Beedie", "Polygon",
    "Avisina", "Peterson", "Aryze", "Onni", "Edgar", "Williams", "Greystar",
    "PC Urban", "Aragon", "Dayhu", "Bosa", "Dawson+Sawyer", "Vanprop",
    "Frame", "Placemaker", "QuadReal", "CF", "Intracrop"
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
VIP_DOMAINS = []  # Configurable later

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

def extract_project_info(subject: str) -> Tuple[str, str, str]:
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
    safe = re.sub(r'[\\/:*?"<>|]', '-', text)
    safe = re.sub(r'-+', '-', safe)
    return safe[:max_length].strip('-')

# =============================================================================
# SERVICE
# =============================================================================

class MailService:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(MailService, cls).__new__(cls)
                    cls._instance.initialized = False
        return cls._instance
    
    def __init__(self):
        if self.initialized:
            return
        
        self.settings = get_settings()
        self.running = False
        self.thread = None
        self.stop_event = threading.Event()
        self.initialized = True
        
    def start(self):
        """Start the background polling thread if enabled."""
        if not _HAS_WIN32:
            logger.warning("Mail Service: Cannot start - pywin32 not available (Windows only)")
            return

        if not self.settings.mail_enabled:
            logger.info("Mail Service: Disabled in settings")
            return

        if self.running:
            return

        logger.info("Mail Service: Starting background polling...")
        self.stop_event.clear()
        self.running = True
        self.thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop the background polling thread."""
        if not self.running:
            return

        logger.info("Mail Service: Stopping...")
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
        self.running = False
        logger.info("Mail Service: Stopped")

    def _poll_loop(self):
        """Main polling loop running in background thread."""
        pythoncom.CoInitialize() # Initialize COM for this thread
        
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

    def _get_outlook(self):
        """Get Outlook Application object securely."""
        if not _HAS_WIN32 or win32com_client is None:
            return None
        try:
            return win32com_client.Dispatch("Outlook.Application")
        except Exception:
            return None

    def _check_inbox(self):
        """Check Inbox for new emails in the last interval."""
        outlook = self._get_outlook()
        if not outlook:
            return

        namespace = outlook.GetNamespace("MAPI")
        inbox = namespace.GetDefaultFolder(6) # 6 = Inbox
        
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
        items.Sort("[ReceivedTime]", True) # Descending
        
        count = 0
        for item in items:
            # Stop if we went past the cutoff
            try:
                if not hasattr(item, "ReceivedTime"): 
                    continue
                    
                received = item.ReceivedTime
                # Pywin32 time conversion
                if hasattr(received, 'timestamp'):
                    dt = datetime.fromtimestamp(received.timestamp())
                else:
                    # Fallback
                    dt = datetime.now() 
                
                if dt < cutoff:
                    break # We are done
                
                # Process
                self._process_email_item(item)
                count += 1
                
                if count > 50: # Safety guard
                    break
                    
            except Exception as e:
                logger.warning(f"Skipping item due to error: {e}")
                continue

    def _process_email_item(self, item) -> bool:
        """Process a single email item."""
        try:
            subject = getattr(item, "Subject", "(no subject)")
            
            # 1. Check if we already processed it (DB check)
            entry_id = getattr(item, "EntryID", "")
            if self._is_processed(entry_id):
                return False

            # 2. Extract Data
            dev, proj, proj_id = extract_project_info(subject)
            
            # 3. Save to Disk (OneDrive)
            output_base = self.settings.mail_output_path
            
            received_time = item.ReceivedTime
            if hasattr(received_time, 'timestamp'):
                received_dt = datetime.fromtimestamp(received_time.timestamp())
            else:
                received_dt = datetime.now()
            
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
                
            # Attachments
            if item.Attachments.Count > 0:
                att_folder = email_folder / "attachments"
                att_folder.mkdir(exist_ok=True)
                for i in range(item.Attachments.Count):
                    att = item.Attachments.Item(i + 1)

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

            # 4. Save to DB (Transient)
            self._save_transient_record(item, proj_id, received_dt)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to process email: {e}")
            return False

    def _is_processed(self, entry_id) -> bool:
        """Check if email ID is already in our DB."""
        db = get_db()
        row = db.execute("SELECT 1 FROM transient_emails WHERE id = ?", (entry_id,)).fetchone()
        return row is not None

    def _save_transient_record(self, item, project_id, received_dt):
        """Save email metadata to SQLite."""
        db = get_db()
        
        entry_id = getattr(item, "EntryID", "")
        subject = getattr(item, "Subject", "")
        sender = getattr(item, "SenderEmailAddress", "")
        body = getattr(item, "Body", "")[:500] # Preview
        
        metadata = {
            "importance": getattr(item, "Importance", 1),
            "dev": extract_project_info(subject)[0],
        }
        
        db.execute("""
            INSERT INTO transient_emails (id, subject, sender, received_at, project_id, body_preview, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (entry_id, subject, sender, received_dt, project_id, body, json.dumps(metadata)))
        db.commit()

    # =========================================================================
    # PST INGESTION
    # =========================================================================

    def ingest_pst(self, pst_path: str) -> Dict:
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
            return {"success": False, "error": "Invalid file type. Only .pst and .ost files are allowed."}

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
        cur = db.execute("INSERT INTO mail_ingestion_log (source_path, status) VALUES (?, ?)", (str(path), "processing"))
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
            db.execute("UPDATE mail_ingestion_log SET status = ?, email_count = ? WHERE id = ?", ("completed", processed_count, ingest_id))
            db.commit()
            
            return {"success": True, "count": processed_count}
            
        except Exception as e:
            db.execute("UPDATE mail_ingestion_log SET status = ?, error_message = ? WHERE id = ?", ("failed", str(e), ingest_id))
            db.commit()
            return {"success": False, "error": str(e)}
        finally:
            pythoncom.CoUninitialize()

    def _process_folder_recursive(self, folder, ingest_id) -> int:
        count = 0
        
        # Items
        try:
            for item in folder.Items:
                 if getattr(item, "Class", 0) == 43: # olMail
                     # Similar processing to regular email but linked to ingest_id
                     if self._process_ingested_item(item, ingest_id):
                         count += 1
        except Exception:
            pass
            
        # Subfolders
        try:
            for sub in folder.Folders:
                count += self._process_folder_recursive(sub, ingest_id)
        except Exception:
            pass
            
        return count

    def _process_ingested_item(self, item, ingest_id) -> bool:
        """Process item from PST."""
        # Check DB
        entry_id = getattr(item, "EntryID", "")
        if self._is_processed(entry_id):
            return False
            
        subject = getattr(item, "Subject", "(no subject)")
        dev, proj, proj_id = extract_project_info(subject)
        
        received_time = getattr(item, "ReceivedTime", datetime.now())
        if hasattr(received_time, 'timestamp'):
            received_dt = datetime.fromtimestamp(received_time.timestamp())
        else:
            received_dt = datetime.now()

        # Save to Transient DB with ingest_id
        db = get_db()
        sender = getattr(item, "SenderEmailAddress", "")
        body = getattr(item, "Body", "")[:500]
        
        metadata = {
            "source": "pst",
            "folder": str(item.Parent.Name) if hasattr(item, "Parent") else ""
        }
        
        db.execute("""
            INSERT INTO transient_emails (id, subject, sender, received_at, project_id, body_preview, metadata, ingestion_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (entry_id, subject, sender, received_dt, proj_id, body, json.dumps(metadata), ingest_id))
        db.commit()
        
        return True

