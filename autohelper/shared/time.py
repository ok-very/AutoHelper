"""
Time utilities.
"""

from datetime import datetime, timezone


def utcnow_iso() -> str:
    """Get current UTC time in ISO format."""
    return datetime.now(timezone.utc).isoformat()
