"""
ID generation utilities.
Uses UUIDs for stable, unique identifiers.
"""

import uuid
from datetime import datetime


def generate_id(prefix: str = "") -> str:
    """Generate a unique ID with optional prefix."""
    uid = uuid.uuid4().hex[:12]
    if prefix:
        return f"{prefix}_{uid}"
    return uid


def generate_request_id() -> str:
    """Generate a request ID for tracing."""
    return f"req_{uuid.uuid4().hex[:16]}"


def generate_file_id() -> str:
    """Generate a file ID."""
    return f"f_{uuid.uuid4().hex[:12]}"


def generate_root_id() -> str:
    """Generate a root ID."""
    return f"root_{uuid.uuid4().hex[:8]}"


def generate_index_run_id() -> str:
    """Generate an index run ID."""
    return f"run_{uuid.uuid4().hex[:12]}"


def generate_ref_id() -> str:
    """Generate a reference ID."""
    return f"ref_{uuid.uuid4().hex[:12]}"


def generate_audit_id() -> str:
    """Generate an audit log entry ID."""
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"aud_{ts}_{uuid.uuid4().hex[:8]}"
