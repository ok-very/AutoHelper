"""
Email draft creation service.

Dual-strategy approach:
1. Microsoft Graph API (primary) — creates draft in user's mailbox via Entra token
2. Outlook COM automation (fallback) — creates draft locally via win32com on Windows
"""

import logging
import platform
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"


class DraftCreationError(Exception):
    """Raised when draft creation fails."""

    def __init__(self, message: str, strategy: str):
        super().__init__(message)
        self.strategy = strategy


def can_use_outlook() -> bool:
    """Check if Outlook COM automation is available (Windows + pywin32)."""
    if platform.system() != "Windows":
        return False
    try:
        import win32com.client  # noqa: F401

        return True
    except ImportError:
        return False


async def create_draft_via_graph(
    token: str,
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    body_type: str = "Text",
) -> dict[str, Any]:
    """
    Create an email draft using the Microsoft Graph API.

    Args:
        token: Microsoft Graph access token with Mail.ReadWrite scope
        to: Recipient email address
        subject: Email subject
        body: Email body content
        cc: CC recipient email address (optional)
        body_type: "Text" or "HTML"

    Returns:
        Dict with id, subject, and webLink of the created draft

    Raises:
        DraftCreationError: If the API call fails
    """
    message: dict[str, Any] = {
        "subject": subject,
        "body": {
            "contentType": body_type,
            "content": body,
        },
        "toRecipients": [
            {"emailAddress": {"address": to}},
        ],
    }

    if cc:
        message["ccRecipients"] = [
            {"emailAddress": {"address": addr.strip()}}
            for addr in cc.split(",")
            if addr.strip()
        ]

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GRAPH_API_BASE}/me/messages",
                json=message,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=15,
            )
    except httpx.RequestError as e:
        logger.error(f"Graph API draft creation request failed: {e}")
        raise DraftCreationError(
            f"Graph API request failed: {e}",
            strategy="graph",
        ) from e

    if response.status_code not in (200, 201):
        error_text = response.text
        logger.error(f"Graph API draft creation failed: {response.status_code} {error_text}")
        raise DraftCreationError(
            f"Graph API returned {response.status_code}: {error_text}",
            strategy="graph",
        )

    data = response.json()
    return {
        "id": data.get("id"),
        "subject": data.get("subject"),
        "web_link": data.get("webLink"),
    }


def create_draft_via_com(
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
) -> dict[str, Any]:
    """
    Create an email draft using Outlook COM automation (Windows only).

    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body content
        cc: CC recipient email address (optional)

    Returns:
        Dict with subject of the created draft

    Raises:
        DraftCreationError: If COM automation fails or is unavailable
    """
    if not can_use_outlook():
        raise DraftCreationError(
            "Outlook COM not available (requires Windows with pywin32 and Outlook installed)",
            strategy="outlook_com",
        )

    try:
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
            mail_item = outlook.CreateItem(0)  # 0 = olMailItem
            mail_item.To = to
            mail_item.Subject = subject
            mail_item.Body = body
            if cc:
                mail_item.CC = cc
            mail_item.Save()

            return {
                "subject": subject,
            }
        finally:
            pythoncom.CoUninitialize()

    except Exception as e:
        logger.error(f"Outlook COM draft creation failed: {e}")
        raise DraftCreationError(
            f"Outlook COM failed: {e}",
            strategy="outlook_com",
        ) from e
