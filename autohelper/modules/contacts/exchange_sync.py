"""Exchange Online sync via PowerShell subprocess.

Builds diff operations, serializes to temp JSON, invokes PowerShell script,
and parses structured JSON results.
"""

import json
import logging
import subprocess
import tempfile
from dataclasses import asdict
from pathlib import Path

from autohelper.config import get_settings

from .types import ContactRecord

logger = logging.getLogger(__name__)

SCRIPTS_DIR = Path(__file__).parent / "powershell"


def _get_auth() -> dict:
    """Build auth dict from settings."""
    settings = get_settings()
    auth: dict[str, str] = {}
    if settings.exchange_email:
        auth["email"] = settings.exchange_email
    if settings.exchange_password:
        auth["password"] = settings.exchange_password
    return auth


def _build_exchange_contact(contact: ContactRecord, managed_prefix: str) -> dict:
    """Map a ContactRecord to Exchange Online contact properties."""
    return {
        "Identity": f"{managed_prefix}{contact.email_primary}",
        "DisplayName": contact.full_name or contact.email_primary,
        "ExternalEmailAddress": contact.email_primary,
        "FirstName": contact.first_name,
        "LastName": contact.last_name,
        "Company": contact.company,
        "Title": contact.job_title,
        "Phone": contact.phone_business,
        "MobilePhone": contact.phone_mobile,
        "StreetAddress": contact.street_address,
        "City": contact.city,
        "StateOrProvince": contact.state,
        "PostalCode": contact.postal_code,
        "CountryOrRegion": contact.country,
        "CustomAttribute1": contact.category_canonical,
    }


def sync_contacts_to_exchange(
    to_create: list[ContactRecord],
    to_update: list[ContactRecord],
    to_delete: list[str],
    managed_prefix: str,
    batch_size: int = 50,
) -> dict:
    """
    Invoke PowerShell to sync contacts to Exchange Online.

    Args:
        to_create: Contacts to create in Exchange
        to_update: Contacts to update in Exchange
        to_delete: Exchange identities to remove
        managed_prefix: Prefix for managed contact identities
        batch_size: Max operations per invocation

    Returns:
        Dict with keys: created, updated, deleted, errors
    """
    # Build operation payload
    operations = {
        "auth": _get_auth(),
        "create": [
            _build_exchange_contact(c, managed_prefix) for c in to_create[:batch_size]
        ],
        "update": [
            _build_exchange_contact(c, managed_prefix) for c in to_update[:batch_size]
        ],
        "delete": to_delete[:batch_size],
    }

    # Write to temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tf:
        json.dump(operations, tf, indent=2)
        input_path = tf.name

    script_path = SCRIPTS_DIR / "sync_contacts.ps1"
    if not script_path.exists():
        logger.error("PowerShell script not found: %s", script_path)
        return {"created": 0, "updated": 0, "deleted": 0, "errors": ["Script not found"]}

    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-ExecutionPolicy", "Bypass",
                "-File", str(script_path),
                "-InputFile", input_path,
            ],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        if result.returncode != 0:
            logger.error("PowerShell sync failed (exit %d): %s", result.returncode, result.stderr)
            return {
                "created": 0,
                "updated": 0,
                "deleted": 0,
                "errors": [f"PowerShell exit code {result.returncode}: {result.stderr[:500]}"],
            }

        # Parse JSON output from PowerShell
        try:
            output = json.loads(result.stdout)
            return output
        except json.JSONDecodeError:
            logger.error("Failed to parse PowerShell output: %s", result.stdout[:500])
            return {
                "created": 0,
                "updated": 0,
                "deleted": 0,
                "errors": ["Failed to parse PowerShell output"],
            }

    except FileNotFoundError:
        logger.error("powershell.exe not found - Exchange sync requires Windows with PowerShell")
        return {
            "created": 0,
            "updated": 0,
            "deleted": 0,
            "errors": ["powershell.exe not found"],
        }
    except subprocess.TimeoutExpired:
        logger.error("PowerShell sync timed out after 300s")
        return {
            "created": 0,
            "updated": 0,
            "deleted": 0,
            "errors": ["PowerShell sync timed out"],
        }
    finally:
        # Clean up temp file
        try:
            Path(input_path).unlink(missing_ok=True)
        except Exception:
            pass


def test_exchange_connection() -> dict:
    """
    Test Exchange Online connectivity.

    Returns:
        Dict with keys: connected (bool), message (str)
    """
    script_path = SCRIPTS_DIR / "test_connection.ps1"

    if not script_path.exists():
        return {"connected": False, "message": "Test script not found"}

    auth_json = json.dumps(_get_auth())

    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-ExecutionPolicy", "Bypass",
                "-File", str(script_path),
                "-AuthJson", auth_json,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        try:
            output = json.loads(result.stdout)
            return output
        except json.JSONDecodeError:
            return {
                "connected": result.returncode == 0,
                "message": result.stdout[:500] or result.stderr[:500],
            }

    except FileNotFoundError:
        return {"connected": False, "message": "powershell.exe not found"}
    except subprocess.TimeoutExpired:
        return {"connected": False, "message": "Connection test timed out"}
