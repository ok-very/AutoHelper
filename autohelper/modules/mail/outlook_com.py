"""
DEPRECATED: Outlook COM helpers partially migrated to AutoHelper.
See: autohelper/modules/mail/service.py

Outlook COM integration for creating drafts.
Uses win32com to interact with Outlook application.

Migration Notes:
- Outlook connection → MailService._get_outlook()
- COM initialization → guarded in MailService with _HAS_WIN32 flag
- Draft creation functions remain here for automail frontend use (not yet migrated)
"""

import win32com.client
from typing import Optional
import pythoncom
from dataclasses import dataclass

@dataclass
class DraftEmail:
    """Email draft to be created in Outlook"""
    to: str
    subject: str
    body: str
    cc: Optional[str] = None
    importance: int = 1  # 0=Low, 1=Normal, 2=High

def create_outlook_draft(draft: DraftEmail) -> dict:
    """
    Create a draft email in Outlook's Drafts folder.
    
    Args:
        draft: DraftEmail object with recipient, subject, body
    
    Returns:
        dict with 'success' status and 'message' or 'error'
    """
    try:
        # Initialize COM for thread safety
        pythoncom.CoInitialize()
        
        # Get Outlook application
        outlook = win32com.client.Dispatch("Outlook.Application")
        
        # Create a new mail item
        # 0 = olMailItem
        mail = outlook.CreateItem(0)
        
        # Set email properties
        mail.To = draft.to
        mail.Subject = draft.subject
        mail.Body = draft.body
        
        if draft.cc:
            mail.CC = draft.cc
        
        mail.Importance = draft.importance
        
        # Save to Drafts (don't send)
        mail.Save()
        
        return {
            "success": True,
            "message": f"Draft created for: {draft.to}",
            "subject": draft.subject
        }
        
    except Exception as e:
        error_msg = str(e)
        
        # Common error handling
        if "Cannot create object" in error_msg or "Class not registered" in error_msg:
            return {
                "success": False,
                "error": "Outlook is not installed or not accessible",
                "details": error_msg
            }
        elif "The remote procedure call failed" in error_msg:
            return {
                "success": False,
                "error": "Outlook is not running. Please open Outlook first.",
                "details": error_msg
            }
        else:
            return {
                "success": False,
                "error": "Failed to create draft",
                "details": error_msg
            }
    finally:
        pythoncom.CoUninitialize()


def create_reply_draft(
    original_sender: str,
    original_subject: str,
    reply_body: str,
    cc: Optional[str] = None
) -> dict:
    """
    Create a reply draft with RE: prefix.
    
    Args:
        original_sender: Email address of original sender
        original_subject: Subject of original email
        reply_body: Body of the reply
        cc: Optional CC recipients
    
    Returns:
        dict with 'success' status
    """
    # Add RE: prefix if not already present
    if not original_subject.upper().startswith("RE:"):
        subject = f"RE: {original_subject}"
    else:
        subject = original_subject
    
    draft = DraftEmail(
        to=original_sender,
        subject=subject,
        body=reply_body,
        cc=cc
    )
    
    return create_outlook_draft(draft)


def check_outlook_available() -> dict:
    """
    Check if Outlook is available and accessible.
    
    Returns:
        dict with 'available' status and 'message'
    """
    try:
        pythoncom.CoInitialize()
        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        
        # Try to access the Drafts folder
        # 16 = olFolderDrafts
        drafts = namespace.GetDefaultFolder(16)
        
        return {
            "available": True,
            "message": f"Outlook is ready. Drafts folder: {drafts.Name}",
            "draft_count": drafts.Items.Count
        }
    except Exception as e:
        return {
            "available": False,
            "error": str(e)
        }
    finally:
        pythoncom.CoUninitialize()


# Test script
if __name__ == "__main__":
    print("Checking Outlook availability...")
    status = check_outlook_available()
    print(f"Status: {status}")
    
    if status.get("available"):
        print("\nCreating test draft...")
        result = create_reply_draft(
            original_sender="test@example.com",
            original_subject="Re: Public Art Project",
            reply_body="Hi,\n\nThank you for your email. I'll review this and get back to you shortly.\n\nBest,\nNeal"
        )
        print(f"Result: {result}")
    else:
        print("Outlook not available. Please ensure Outlook is installed and running.")
