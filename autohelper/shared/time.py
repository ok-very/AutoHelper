"""
Time utilities.
"""

from datetime import UTC, datetime


def utcnow_iso() -> str:
    """Get current UTC time in ISO format."""
    return datetime.now(UTC).isoformat()
