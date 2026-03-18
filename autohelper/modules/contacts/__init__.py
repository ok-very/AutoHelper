"""Contact Sync module - polls CSV, diffs, syncs to Exchange Online."""

from .router import router
from .service import ContactSyncService

__all__ = ["router", "ContactSyncService"]
