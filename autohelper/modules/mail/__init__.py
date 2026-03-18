from .router import router as mail_router
from .schemas import (
    IngestionLogEntry,
    IngestionLogList,
    IngestRequest,
    IngestResponse,
    MailServiceStatus,
    TransientEmail,
    TransientEmailList,
    TriageRequest,
    TriageResponse,
)
from .service import MailService

__all__ = [
    "MailService",
    "mail_router",
    "MailServiceStatus",
    "TransientEmail",
    "TransientEmailList",
    "IngestionLogEntry",
    "IngestionLogList",
    "IngestRequest",
    "IngestResponse",
    "TriageRequest",
    "TriageResponse",
]
