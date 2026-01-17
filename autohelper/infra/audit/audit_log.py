"""
Audit log writer - append-only log for all operations.
Records before/after state for filesystem operations.
"""

import json
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from autohelper.db import get_db
from autohelper.shared.ids import generate_audit_id
from autohelper.shared.logging import get_logger, get_request_context
from autohelper.shared.types import RequestContext

logger = get_logger(__name__)

T = TypeVar("T")


class AuditLogger:
    """Append-only audit log writer."""
    
    def log(
        self,
        verb: str,
        request_data: dict[str, Any] | None = None,
        result_data: dict[str, Any] | None = None,
        before_path: str | None = None,
        after_path: str | None = None,
        status: str = "success",
        error_code: str | None = None,
        context: RequestContext | None = None,
    ) -> str:
        """
        Write an audit log entry.
        
        Args:
            verb: Operation name (e.g., "file.rename", "index.rebuild")
            request_data: Request payload (will be JSON serialized)
            result_data: Result payload (will be JSON serialized)
            before_path: Path before operation (for moves/renames)
            after_path: Path after operation
            status: "success" or "error"
            error_code: Error code if status is "error"
            context: Request context (uses current context if None)
        
        Returns:
            Generated audit_id
        """
        if context is None:
            context = get_request_context()
        
        audit_id = generate_audit_id()
        
        db = get_db()
        db.execute(
            """
            INSERT INTO audit_log (
                audit_id, actor, verb, work_item_id, context_id,
                request_json, result_json, before_path, after_path,
                status, error_code, idempotency_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                audit_id,
                context.actor if context else "system",
                verb,
                context.work_item_id if context else None,
                context.context_id if context else None,
                json.dumps(request_data) if request_data else None,
                json.dumps(result_data) if result_data else None,
                before_path,
                after_path,
                status,
                error_code,
                context.idempotency_key if context else None,
            ),
        )
        db.commit()
        
        logger.debug(f"Audit: {verb} [{status}] -> {audit_id}")
        return audit_id
    
    def check_idempotency(self, key: str) -> dict[str, Any] | None:
        """
        Check if an idempotency key was already used.
        
        Returns:
            Previous result if key exists, None otherwise
        """
        if not key:
            return None
        
        db = get_db()
        cursor = db.execute(
            """
            SELECT result_json, status, error_code
            FROM audit_log
            WHERE idempotency_key = ?
            ORDER BY at DESC
            LIMIT 1
            """,
            (key,),
        )
        row = cursor.fetchone()
        
        if row:
            return {
                "result": json.loads(row["result_json"]) if row["result_json"] else None,
                "status": row["status"],
                "error_code": row["error_code"],
            }
        
        return None


# Global audit logger instance
_audit_logger = AuditLogger()


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger."""
    return _audit_logger


def audit_operation(verb: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to automatically audit a function.
    
    Usage:
        @audit_operation("file.rename")
        def rename_file(old_path: str, new_path: str) -> dict:
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            audit = get_audit_logger()
            context = get_request_context()
            
            # Check idempotency
            if context and context.idempotency_key:
                existing = audit.check_idempotency(context.idempotency_key)
                if existing and existing["status"] == "success":
                    logger.info(f"Idempotency hit for {verb}: {context.idempotency_key}")
                    return existing["result"]
            
            # Prepare request data from kwargs
            request_data = {
                k: str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
                for k, v in kwargs.items()
            }
            
            try:
                result = func(*args, **kwargs)
                
                # Convert result for logging
                result_data = result if isinstance(result, dict) else {"result": str(result)}
                
                audit.log(
                    verb=verb,
                    request_data=request_data,
                    result_data=result_data,
                    status="success",
                    context=context,
                )
                
                return result
                
            except Exception as e:
                error_code = getattr(e, "code", "UNKNOWN")
                
                audit.log(
                    verb=verb,
                    request_data=request_data,
                    result_data={"error": str(e)},
                    status="error",
                    error_code=error_code,
                    context=context,
                )
                
                raise
        
        return wrapper
    return decorator
