"""
DEPRECATED: This module has been migrated to AutoHelper.
See: autohelper/modules/mail/service.py

Email Parser - Watches Outlook inbox and extracts metadata to organized folders.

Triggers: Can run as a scheduled task or watch for new emails in real-time.
Output: Saves emails to OneDrive/Emails/{ProjectName}/{date_subject}/

Migration Notes:
- Core polling logic → MailService._poll_loop(), _check_inbox()
- PST ingestion → MailService.ingest_pst()
- extract_project_info(), clean_subject() → mail/service.py
- DB storage replaces file-based metadata.json output
"""

import win32com.client
import os
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
import time
from typing import Optional, Dict, List, Tuple

# =============================================================================
# CONFIGURATION
# =============================================================================

# Base output directory (OneDrive syncs this)
OUTPUT_BASE = Path(os.environ.get('USERPROFILE', '')) / "OneDrive" / "Emails"

# Known developers/clients for project detection
KNOWN_DEVELOPERS = [
    "Qualex", "Anthem", "PCI", "Holborn", "Intracorp", "Beedie", "Polygon",
    "Avisina", "Peterson", "Aryze", "Onni", "Edgar", "Williams", "Greystar",
    "PC Urban", "Aragon", "Dayhu", "Bosa", "Dawson+Sawyer", "Vanprop",
    "Frame", "Placemaker", "QuadReal", "CF", "Intracrop"
]

# VIP domains (placeholder - add as needed)
VIP_DOMAINS: List[str] = [
    # "@important-client.com",
]

# Urgency keywords
URGENCY_KEYWORDS = ["urgent", "asap", "deadline", "immediately", "critical", "time-sensitive"]

# Action type detection patterns
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

# =============================================================================
# PARSING FUNCTIONS
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
    """
    cleaned = clean_subject(subject)
    
    if " - " not in cleaned:
        return "", "", "_Uncategorized"
    
    parts = [p.strip() for p in cleaned.split(" - ")]
    
    if len(parts) >= 2:
        developer = parts[0]
        project = parts[1]
        
        # Validate developer is known
        developer_matched = any(dev.lower() in developer.lower() for dev in KNOWN_DEVELOPERS)
        
        if developer_matched:
            full_project_id = f"{developer} - {project}"
            return developer, project, full_project_id
    
    return "", "", "_Uncategorized"


def extract_construction_phase(subject: str) -> str:
    """Extract Phase D, Phase E, Phase 1, etc. from subject."""
    cleaned = clean_subject(subject)
    match = re.search(r'Phase\s+([A-Z0-9]+)', cleaned, re.IGNORECASE)
    if match:
        return f"Phase {match.group(1).upper()}"
    return ""


def extract_mentioned_dates(text: str) -> List[datetime]:
    """
    Extract dates mentioned in email body/subject.
    Looks for patterns like: Jan 15, January 15, 2026-01-15, 01/15/2026, etc.
    """
    dates = []
    now = datetime.now()
    
    # Pattern: Month Day, Year (Jan 15, 2026 or January 15, 2026)
    pattern1 = r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:,?\s+\d{4})?'
    for match in re.finditer(pattern1, text, re.IGNORECASE):
        try:
            date_str = match.group()
            # Add current year if not present
            if not re.search(r'\d{4}', date_str):
                date_str += f", {now.year}"
            parsed = datetime.strptime(date_str.replace(",", ""), "%B %d %Y")
            dates.append(parsed)
        except ValueError:
            pass
    
    # Pattern: YYYY-MM-DD
    pattern2 = r'\d{4}-\d{2}-\d{2}'
    for match in re.finditer(pattern2, text):
        try:
            dates.append(datetime.strptime(match.group(), "%Y-%m-%d"))
        except ValueError:
            pass
    
    # Pattern: relative dates like "tomorrow", "next week", "Friday"
    if "tomorrow" in text.lower():
        dates.append(now + timedelta(days=1))
    if "next week" in text.lower():
        dates.append(now + timedelta(days=7))
    
    return dates


def calculate_priority(
    subject: str,
    body: str,
    received_time: datetime,
    sender_email: str,
    has_attachments: bool
) -> Tuple[int, List[str]]:
    """
    Calculate priority score (1-5) based on multiple factors.
    Returns: (priority, list of factors that contributed)
    """
    priority = 3  # Default
    factors = []
    now = datetime.now()
    
    full_text = f"{subject} {body}".lower()
    
    # Factor 1: Urgency keywords (+2)
    for keyword in URGENCY_KEYWORDS:
        if keyword.lower() in full_text:
            priority = min(5, priority + 2)
            factors.append(f"Urgency keyword: {keyword}")
            break
    
    # Factor 2: Mentioned dates - closer = higher priority
    mentioned_dates = extract_mentioned_dates(f"{subject} {body}")
    if mentioned_dates:
        earliest = min(mentioned_dates)
        days_until = (earliest - now).days
        if days_until < 0:
            priority = 5
            factors.append(f"Overdue: date mentioned was {abs(days_until)} days ago")
        elif days_until <= 1:
            priority = min(5, priority + 2)
            factors.append(f"Due within 1 day")
        elif days_until <= 3:
            priority = min(5, priority + 1)
            factors.append(f"Due within 3 days ({earliest.strftime('%Y-%m-%d')})")
        elif days_until <= 7:
            factors.append(f"Due within 1 week ({earliest.strftime('%Y-%m-%d')})")
    
    # Factor 3: Email age (lead time since received)
    email_age_hours = (now - received_time).total_seconds() / 3600
    if email_age_hours > 48:  # Over 2 days old
        priority = min(5, priority + 1)
        factors.append(f"Email age: {email_age_hours:.0f} hours (may need response)")
    
    # Factor 4: VIP sender
    sender_domain = sender_email.split("@")[-1] if "@" in sender_email else ""
    if any(vip in sender_email.lower() for vip in VIP_DOMAINS):
        priority = min(5, priority + 1)
        factors.append(f"VIP sender: {sender_email}")
    
    # Factor 5: Has attachments (slight bump)
    if has_attachments and "invoice" in full_text:
        priority = min(5, priority + 1)
        factors.append("Invoice with attachment")
    
    return priority, factors


def detect_action_type(subject: str, body: str) -> str:
    """Detect the action type based on content patterns."""
    full_text = f"{subject} {body}".lower()
    
    for action_type, patterns in ACTION_PATTERNS.items():
        for pattern in patterns:
            if pattern.lower() in full_text:
                return action_type
    
    return "General"


def detect_stakeholder_type(sender_email: str) -> str:
    """Classify sender based on email domain."""
    email_lower = sender_email.lower()
    
    if "@ballardfineart.com" in email_lower:
        return "Internal"
    elif "@monday.com" in email_lower:
        return "System"
    elif any(gov in email_lower for gov in ["@city", "@gov", ".gov", "@vancouver.ca", "@burnaby.ca"]):
        return "Government"
    else:
        return "External"


def make_safe_filename(text: str, max_length: int = 50) -> str:
    """Convert text to a safe filename."""
    # Replace problematic characters
    safe = re.sub(r'[\\/:*?"<>|]', '-', text)
    # Collapse multiple dashes
    safe = re.sub(r'-+', '-', safe)
    # Truncate
    return safe[:max_length].strip('-')


def extract_keywords(subject: str, body: str) -> List[str]:
    """Extract relevant keywords from email content."""
    keywords = []
    full_text = f"{subject} {body}".lower()
    
    # Document types
    doc_keywords = ["invoice", "contract", "proposal", "report", "manual", "plaque", 
                    "drawing", "PPAP", "DPAP", "TOR", "acceptance"]
    for kw in doc_keywords:
        if kw.lower() in full_text:
            keywords.append(kw)
    
    # Project stages
    stage_keywords = ["selection panel", "fabrication", "installation", "closeout",
                      "final documentation", "artist contract"]
    for kw in stage_keywords:
        if kw.lower() in full_text:
            keywords.append(kw)
    
    return list(set(keywords))


# =============================================================================
# EMAIL PROCESSING
# =============================================================================

def process_email(email_item, output_base: Path) -> Optional[Dict]:
    """
    Process a single email and save to organized folder structure.
    Returns metadata dict on success, None on failure.
    """
    try:
        subject = email_item.Subject or "(no subject)"
        body = email_item.Body or ""
        html_body = email_item.HTMLBody or ""
        sender_email = str(email_item.SenderEmailAddress or "")
        sender_name = str(email_item.SenderName or "")
        received_time = email_item.ReceivedTime
        has_attachments = email_item.Attachments.Count > 0
        
        # Convert received_time to datetime
        if hasattr(received_time, 'timestamp'):
            received_dt = datetime.fromtimestamp(received_time.timestamp())
        else:
            received_dt = datetime.now()
        
        # Extract project info
        developer, project, project_id = extract_project_info(subject)
        construction_phase = extract_construction_phase(subject)
        
        # Calculate priority
        priority, priority_factors = calculate_priority(
            subject, body, received_dt, sender_email, has_attachments
        )
        
        # Detect action type and stakeholder
        action_type = detect_action_type(subject, body)
        stakeholder_type = detect_stakeholder_type(sender_email)
        
        # Extract keywords
        keywords = extract_keywords(subject, body)
        
        # Create folder name
        date_str = received_dt.strftime("%Y-%m-%d")
        safe_subject = make_safe_filename(clean_subject(subject))
        folder_name = f"{date_str}_{safe_subject}"
        
        # Create output path
        project_folder = output_base / make_safe_filename(project_id, 100)
        email_folder = project_folder / folder_name
        attachments_folder = email_folder / "attachments"
        
        # Create directories
        email_folder.mkdir(parents=True, exist_ok=True)
        if has_attachments:
            attachments_folder.mkdir(exist_ok=True)
        
        # Build metadata
        metadata = {
            "id": str(email_item.EntryID) if hasattr(email_item, 'EntryID') else "",
            "subject": subject,
            "from": sender_email,
            "fromName": sender_name,
            "to": str(email_item.To or ""),
            "cc": str(email_item.CC or ""),
            "receivedDateTime": received_dt.isoformat(),
            "processedDateTime": datetime.now().isoformat(),
            "hasAttachments": has_attachments,
            "importance": str(email_item.Importance) if hasattr(email_item, 'Importance') else "",
            
            # Extracted metadata
            "projectId": project_id,
            "developer": developer,
            "projectName": project,
            "constructionPhase": construction_phase,
            "actionType": action_type,
            "stakeholderType": stakeholder_type,
            "priority": priority,
            "priorityFactors": priority_factors,
            "extractedKeywords": keywords,
        }
        
        # Save metadata
        with open(email_folder / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        # Save body as HTML
        with open(email_folder / "body.html", "w", encoding="utf-8") as f:
            f.write(html_body or body)
        
        # Save body as plain text
        with open(email_folder / "body.txt", "w", encoding="utf-8") as f:
            f.write(body)
        
        # Save attachments
        for i in range(email_item.Attachments.Count):
            attachment = email_item.Attachments.Item(i + 1)
            attach_name = make_safe_filename(str(attachment.FileName), 100)
            attachment.SaveAsFile(str(attachments_folder / attach_name))
        
        return metadata
        
    except Exception as e:
        print(f"Error processing email: {e}")
        return None


def get_outlook_inbox(folder_name: str = "Inbox"):
    """Get the Outlook inbox folder."""
    outlook = win32com.client.Dispatch("Outlook.Application")
    namespace = outlook.GetNamespace("MAPI")
    inbox = namespace.GetDefaultFolder(6)  # 6 = Inbox
    return inbox


def process_new_emails(hours_back: int = 24, output_base: Optional[Path] = None):
    """Process emails received in the last N hours."""
    if output_base is None:
        output_base = OUTPUT_BASE
    
    output_base.mkdir(parents=True, exist_ok=True)
    
    inbox = get_outlook_inbox()
    cutoff = datetime.now() - timedelta(hours=hours_back)
    
    processed = 0
    errors = 0
    
    for item in inbox.Items:
        try:
            if hasattr(item, 'ReceivedTime'):
                received = item.ReceivedTime
                if hasattr(received, 'timestamp'):
                    received_dt = datetime.fromtimestamp(received.timestamp())
                    if received_dt > cutoff:
                        result = process_email(item, output_base)
                        if result:
                            print(f"✓ {result['projectId']}: {result['subject'][:50]}...")
                            processed += 1
                        else:
                            errors += 1
        except Exception as e:
            errors += 1
            continue
    
    print(f"\nProcessed: {processed}, Errors: {errors}")
    return processed


def watch_inbox(poll_interval_seconds: int = 30, output_base: Optional[Path] = None):
    """
    Continuously watch inbox for new emails.
    Poll every N seconds for new messages.
    """
    if output_base is None:
        output_base = OUTPUT_BASE
    
    output_base.mkdir(parents=True, exist_ok=True)
    
    print(f"Watching inbox (polling every {poll_interval_seconds}s)...")
    print(f"Output: {output_base}")
    print("Press Ctrl+C to stop.\n")
    
    last_check = datetime.now()
    
    while True:
        try:
            inbox = get_outlook_inbox()
            new_count = 0
            
            for item in inbox.Items:
                try:
                    if hasattr(item, 'ReceivedTime'):
                        received = item.ReceivedTime
                        if hasattr(received, 'timestamp'):
                            received_dt = datetime.fromtimestamp(received.timestamp())
                            if received_dt > last_check:
                                result = process_email(item, output_base)
                                if result:
                                    print(f"[{datetime.now().strftime('%H:%M:%S')}] New: {result['projectId']}: {result['subject'][:40]}...")
                                    new_count += 1
                except Exception:
                    continue
            
            last_check = datetime.now()
            
            if new_count == 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Checked - no new emails", end="\r")
            
            time.sleep(poll_interval_seconds)
            
        except KeyboardInterrupt:
            print("\nStopped watching.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(poll_interval_seconds)


class OutlookEventHandler:
    """Handler for Outlook COM events."""
    
    def __init__(self, output_base: Path):
        self.output_base = output_base
        self.processed_ids = set()
    
    def OnNewMailEx(self, entry_ids):
        """Called when new mail arrives in Outlook."""
        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
            namespace = outlook.GetNamespace("MAPI")
            
            # entry_ids is comma-separated list of entry IDs
            for entry_id in entry_ids.split(","):
                entry_id = entry_id.strip()
                if entry_id in self.processed_ids:
                    continue
                    
                try:
                    item = namespace.GetItemFromID(entry_id)
                    result = process_email(item, self.output_base)
                    if result:
                        self.processed_ids.add(entry_id)
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] NEW: {result['projectId']}: {result['subject'][:40]}...")
                except Exception as e:
                    print(f"Error processing new mail: {e}")
                    
        except Exception as e:
            print(f"Error in OnNewMailEx: {e}")


def watch_outlook_events(output_base: Optional[Path] = None):
    """
    Watch for new emails using Outlook COM events.
    This triggers immediately when new mail arrives (no polling delay).
    """
    import pythoncom
    
    if output_base is None:
        output_base = OUTPUT_BASE
    
    output_base.mkdir(parents=True, exist_ok=True)
    
    print("Connecting to Outlook events...")
    print(f"Output: {output_base}")
    print("Waiting for new emails (triggers instantly)...")
    print("Press Ctrl+C to stop.\n")
    
    try:
        # Initialize COM
        pythoncom.CoInitialize()
        
        # Get Outlook application
        outlook = win32com.client.DispatchWithEvents(
            "Outlook.Application", 
            type('OutlookEvents', (), {
                'output_base': output_base,
                'processed_ids': set(),
                'OnNewMailEx': lambda self, entry_ids: _handle_new_mail(entry_ids, self.output_base, self.processed_ids)
            })
        )
        
        print("Connected! Listening for new emails...")
        
        # Message loop - keeps the script running and processing events
        while True:
            pythoncom.PumpWaitingMessages()
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nStopped watching.")
    except Exception as e:
        print(f"Error setting up Outlook events: {e}")
        print("Falling back to polling mode...")
        watch_inbox(poll_interval_seconds=10, output_base=output_base)
    finally:
        pythoncom.CoUninitialize()


def _handle_new_mail(entry_ids: str, output_base: Path, processed_ids: set):
    """Handle new mail event."""
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        
        for entry_id in entry_ids.split(","):
            entry_id = entry_id.strip()
            if entry_id in processed_ids:
                continue
                
            try:
                item = namespace.GetItemFromID(entry_id)
                result = process_email(item, output_base)
                if result:
                    processed_ids.add(entry_id)
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ NEW: {result['projectId']}: {result['subject'][:40]}...")
            except Exception as e:
                print(f"Error processing: {e}")
                
    except Exception as e:
        print(f"Error handling new mail: {e}")


def watch_ost_file(output_base: Optional[Path] = None):
    """
    Watch Outlook's OST file for changes and trigger processing.
    Falls back if Outlook events aren't available.
    """
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        print("Installing watchdog...")
        import subprocess
        subprocess.run(["pip", "install", "watchdog", "-q"])
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    
    if output_base is None:
        output_base = OUTPUT_BASE
    
    # Find Outlook data folder
    outlook_data = Path(os.environ.get('LOCALAPPDATA', '')) / "Microsoft" / "Outlook"
    
    class OSTHandler(FileSystemEventHandler):
        def __init__(self):
            self.last_trigger = datetime.now()
            self.debounce_seconds = 5  # Don't trigger more than once per 5 seconds
        
        def on_modified(self, event):
            if event.src_path.endswith('.ost') or event.src_path.endswith('.pst'):
                now = datetime.now()
                if (now - self.last_trigger).seconds >= self.debounce_seconds:
                    self.last_trigger = now
                    print(f"[{now.strftime('%H:%M:%S')}] Outlook data changed, checking for new emails...")
                    process_new_emails(hours_back=1, output_base=output_base)
    
    print(f"Watching Outlook data folder: {outlook_data}")
    print(f"Output: {output_base}")
    print("Press Ctrl+C to stop.\n")
    
    observer = Observer()
    observer.schedule(OSTHandler(), str(outlook_data), recursive=False)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\nStopped watching.")
    
    observer.join()


# =============================================================================
# PST FILE PROCESSING
# =============================================================================

def process_email_from_pst(message, output_base: Path, skip_attachments: bool = False) -> Optional[Dict]:
    """
    Process a single email from PST file (via Outlook MAPI).
    Similar to process_email but with option to skip attachments.
    """
    try:
        subject = str(message.Subject or "(no subject)")
        body = str(message.Body or "")
        html_body = str(message.HTMLBody or "") if hasattr(message, 'HTMLBody') else ""
        sender_email = str(message.SenderEmailAddress or "")
        sender_name = str(message.SenderName or "")
        received_time = message.ReceivedTime
        has_attachments = message.Attachments.Count > 0 if hasattr(message, 'Attachments') else False
        
        # Convert received_time
        if hasattr(received_time, 'timestamp'):
            received_dt = datetime.fromtimestamp(received_time.timestamp())
        elif hasattr(received_time, 'year'):
            received_dt = datetime(received_time.year, received_time.month, received_time.day)
        else:
            received_dt = datetime.now()
        
        # Extract project info
        developer, project, project_id = extract_project_info(subject)
        construction_phase = extract_construction_phase(subject)
        
        # Calculate priority
        priority, priority_factors = calculate_priority(
            subject, body, received_dt, sender_email, has_attachments
        )
        
        # Detect action type and stakeholder
        action_type = detect_action_type(subject, body)
        stakeholder_type = detect_stakeholder_type(sender_email)
        
        # Extract keywords
        keywords = extract_keywords(subject, body)
        
        # Create folder name
        date_str = received_dt.strftime("%Y-%m-%d")
        safe_subject = make_safe_filename(clean_subject(subject))
        folder_name = f"{date_str}_{safe_subject}"
        
        # Create output path
        project_folder = output_base / make_safe_filename(project_id, 100)
        email_folder = project_folder / folder_name
        
        # Skip if already processed
        if email_folder.exists():
            return None
        
        # Create directories
        email_folder.mkdir(parents=True, exist_ok=True)
        
        # Build metadata
        metadata = {
            "id": str(message.EntryID) if hasattr(message, 'EntryID') else "",
            "subject": subject,
            "from": sender_email,
            "fromName": sender_name,
            "to": str(message.To or ""),
            "cc": str(message.CC or ""),
            "receivedDateTime": received_dt.isoformat(),
            "processedDateTime": datetime.now().isoformat(),
            "hasAttachments": has_attachments,
            "importance": str(message.Importance) if hasattr(message, 'Importance') else "",
            
            # Extracted metadata
            "projectId": project_id,
            "developer": developer,
            "projectName": project,
            "constructionPhase": construction_phase,
            "actionType": action_type,
            "stakeholderType": stakeholder_type,
            "priority": priority,
            "priorityFactors": priority_factors,
            "extractedKeywords": keywords,
            "source": "pst_archive",
        }
        
        # Save metadata
        with open(email_folder / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        # Save body
        with open(email_folder / "body.html", "w", encoding="utf-8") as f:
            f.write(html_body or body)
        
        with open(email_folder / "body.txt", "w", encoding="utf-8") as f:
            f.write(body)
        
        # Save attachments (unless skipped)
        if has_attachments and not skip_attachments:
            attachments_folder = email_folder / "attachments"
            attachments_folder.mkdir(exist_ok=True)
            for i in range(message.Attachments.Count):
                try:
                    attachment = message.Attachments.Item(i + 1)
                    attach_name = make_safe_filename(str(attachment.FileName), 100)
                    attachment.SaveAsFile(str(attachments_folder / attach_name))
                except Exception:
                    pass
        
        return metadata
        
    except Exception as e:
        return None


def process_folder_recursively(folder, output_base: Path, skip_attachments: bool, stats: dict):
    """Process all emails in a folder and its subfolders."""
    try:
        # Process items in this folder
        for item in folder.Items:
            try:
                if hasattr(item, 'Subject'):  # It's an email
                    result = process_email_from_pst(item, output_base, skip_attachments)
                    if result:
                        stats['processed'] += 1
                        if stats['processed'] % 100 == 0:
                            print(f"  Processed: {stats['processed']} emails...")
                    else:
                        stats['skipped'] += 1
            except Exception:
                stats['errors'] += 1
        
        # Recurse into subfolders
        for subfolder in folder.Folders:
            process_folder_recursively(subfolder, output_base, skip_attachments, stats)
            
    except Exception as e:
        print(f"  Error processing folder: {e}")


def process_pst_file(pst_path: str, output_base: Optional[Path] = None, skip_attachments: bool = False) -> dict:
    """
    Process all emails from a PST file using Outlook MAPI.
    
    Args:
        pst_path: Path to the .pst file
        output_base: Output directory (default: OUTPUT_BASE)
        skip_attachments: If True, don't extract attachments (faster for archives)
    
    Returns:
        dict with processing stats
    """
    if output_base is None:
        output_base = OUTPUT_BASE
    
    pst_path = Path(pst_path).resolve()
    if not pst_path.exists():
        return {"error": f"PST file not found: {pst_path}"}
    
    print(f"Processing PST file: {pst_path}")
    print(f"Output: {output_base}")
    print(f"Skip attachments: {skip_attachments}")
    print()
    
    output_base.mkdir(parents=True, exist_ok=True)
    
    stats = {'processed': 0, 'skipped': 0, 'errors': 0}
    
    try:
        # Connect to Outlook
        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        
        # Add the PST file to Outlook
        print("Adding PST to Outlook...")
        namespace.AddStore(str(pst_path))
        
        # Find the added store (it will be the last one or match the filename)
        pst_folder = None
        for folder in namespace.Folders:
            if pst_path.stem.lower() in folder.Name.lower():
                pst_folder = folder
                break
        
        if not pst_folder:
            # Try to get the last added folder
            pst_folder = namespace.Folders.Item(namespace.Folders.Count)
        
        print(f"Found PST root: {pst_folder.Name}")
        print(f"Processing all folders...")
        
        # Process all folders recursively
        process_folder_recursively(pst_folder, output_base, skip_attachments, stats)
        
        # Remove the PST from Outlook (cleanup)
        print("\nRemoving PST from Outlook session...")
        namespace.RemoveStore(pst_folder)
        
    except Exception as e:
        return {"error": str(e), **stats}
    
    print(f"\n=== PST Processing Complete ===")
    print(f"  Processed: {stats['processed']}")
    print(f"  Skipped (already exists): {stats['skipped']}")
    print(f"  Errors: {stats['errors']}")
    
    return stats


def process_all_sources(
    pst_path: Optional[str] = None,
    hours_back: int = 24,
    output_base: Optional[Path] = None,
    skip_pst_attachments: bool = True
) -> dict:
    """
    Process emails from all sources:
    1. Current Outlook inbox (last N hours)
    2. PST archive file (if provided)
    
    Args:
        pst_path: Optional path to legacy PST archive
        hours_back: Hours to look back in live inbox
        output_base: Output directory
        skip_pst_attachments: Skip attachments in PST (default: True for speed)
    
    Returns:
        dict with combined stats
    """
    if output_base is None:
        output_base = OUTPUT_BASE
    
    results = {"inbox": {}, "pst": {}}
    
    # Process live inbox
    print("=" * 50)
    print("PROCESSING LIVE INBOX")
    print("=" * 50)
    inbox_count = process_new_emails(hours_back=hours_back, output_base=output_base)
    results["inbox"] = {"processed": inbox_count}
    
    # Process PST if provided
    if pst_path:
        print("\n" + "=" * 50)
        print("PROCESSING PST ARCHIVE")
        print("=" * 50)
        pst_stats = process_pst_file(pst_path, output_base, skip_attachments=skip_pst_attachments)
        results["pst"] = pst_stats
    
    print("\n" + "=" * 50)
    print("ALL SOURCES COMPLETE")
    print("=" * 50)
    
    return results


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Email Parser - Process Outlook emails with intelligent metadata extraction",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python email_parser.py --hours 24               # Process last 24 hours from inbox
  python email_parser.py --pst archive.pst        # Process PST file (skip attachments)
  python email_parser.py --all --pst archive.pst  # Process inbox + PST archive
  python email_parser.py --watch                  # Poll inbox every 30 seconds
  python email_parser.py --events                 # Instant trigger on new mail
        """
    )
    
    # Mode selection (mutually exclusive)
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--watch", action="store_true", 
                            help="Watch inbox by polling every N seconds")
    mode_group.add_argument("--events", action="store_true", 
                            help="Watch using Outlook events (instant trigger, recommended)")
    mode_group.add_argument("--ost", action="store_true", 
                            help="Watch OST/PST file for changes (fallback)")
    mode_group.add_argument("--all", action="store_true",
                            help="Process all sources: inbox + PST archive")
    
    # Options
    parser.add_argument("--hours", type=int, default=24, 
                        help="Process emails from last N hours (default: 24)")
    parser.add_argument("--output", type=str, 
                        help="Output directory override")
    parser.add_argument("--interval", type=int, default=30, 
                        help="Poll interval in seconds for --watch mode (default: 30)")
    parser.add_argument("--pst", type=str,
                        help="Path to PST file to process")
    parser.add_argument("--with-attachments", action="store_true",
                        help="Also extract attachments from PST (slow for large archives)")
    
    args = parser.parse_args()
    
    output = Path(args.output) if args.output else OUTPUT_BASE
    
    if args.events:
        # Instant trigger on new mail via Outlook COM events
        watch_outlook_events(output_base=output)
    elif args.ost:
        # File system watcher on OST file
        watch_ost_file(output_base=output)
    elif args.watch:
        # Polling mode
        watch_inbox(poll_interval_seconds=args.interval, output_base=output)
    elif args.all:
        # Process all sources
        process_all_sources(
            pst_path=args.pst,
            hours_back=args.hours,
            output_base=output,
            skip_pst_attachments=not args.with_attachments
        )
    elif args.pst:
        # PST only
        process_pst_file(
            pst_path=args.pst, 
            output_base=output, 
            skip_attachments=not args.with_attachments
        )
    else:
        # One-time inbox processing
        print(f"Processing emails from last {args.hours} hours...")
        process_new_emails(hours_back=args.hours, output_base=output)

