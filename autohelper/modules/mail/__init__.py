from .service import MailService
from .router import router as mail_router
from .schemas import (
    MailServiceStatus,
    TransientEmail,
    TransientEmailList,
    IngestionLogEntry,
    IngestionLogList,
    IngestRequest,
    IngestResponse,
)

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
]
