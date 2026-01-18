"""
Application factory - builds FastAPI app with all middleware and routes.
Pattern mirrors AutoArt's buildApp().
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from autohelper.config import Settings, get_settings
from autohelper.db import get_db, init_db
from autohelper.db.migrate import run_migrations

# Import routers
from autohelper.modules.health.router import router as health_router
from autohelper.modules.index.router import router as index_router
from autohelper.modules.search.router import router as search_router
from autohelper.modules.reference.router import router as ref_router
from autohelper.modules.mail.router import router as mail_router
from autohelper.shared.errors import AutoHelperError
from autohelper.shared.ids import generate_request_id
from autohelper.shared.logging import (
    clear_request_context,
    get_logger,
    set_request_context,
    setup_logging,
)
from autohelper.shared.types import RequestContext

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan - startup and shutdown."""
    settings = get_settings()
    
    # Setup logging
    setup_logging(settings.log_level)
    logger.info("Starting AutoHelper...")
    
    # Initialize database
    db = init_db(settings.db_path)
    logger.info(f"Database: {settings.db_path}")
    
    # Run migrations
    applied = run_migrations(db)
    if applied:
        logger.info(f"Applied {len(applied)} migrations")
    
    logger.info("AutoHelper started")
    
    # Start Mail Service
    from autohelper.modules.mail import MailService
    MailService().start()
    
    yield
    
    # Shutdown
    logger.info("Shutting down AutoHelper...")
    MailService().stop()
    db = get_db()
    db.close()
    logger.info("AutoHelper stopped")


def build_app(settings: Settings | None = None) -> FastAPI:
    """
    Build the FastAPI application.
    
    Args:
        settings: Optional settings override (useful for testing)
    
    Returns:
        Configured FastAPI application
    """
    if settings is None:
        settings = get_settings()
    
    app = FastAPI(
        title="AutoHelper",
        description="Local-first filesystem orchestration service",
        version="0.1.0",
        lifespan=lifespan,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Request context middleware
    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next: Any) -> Response:
        """Attach request context for logging and tracing."""
        ctx = RequestContext(
            request_id=request.headers.get("X-Request-ID", generate_request_id()),
            work_item_id=request.headers.get("X-Work-Item-ID"),
            context_id=request.headers.get("X-Context-ID"),
            actor=request.headers.get("X-Actor", "system"),
            idempotency_key=request.headers.get("X-Idempotency-Key"),
        )
        set_request_context(ctx)
        
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = ctx.request_id
            return response
        finally:
            clear_request_context()
    
    # Exception handler for AutoHelperError
    @app.exception_handler(AutoHelperError)
    async def autohelper_error_handler(
        request: Request, exc: AutoHelperError
    ) -> JSONResponse:
        """Handle AutoHelperError with consistent JSON response."""
        ctx = getattr(request.state, "context", None)
        
        return JSONResponse(
            status_code=exc.http_status,
            content={
                "error": exc.to_dict(),
                "request_id": getattr(ctx, "request_id", None) if ctx else None,
                "work_item_id": getattr(ctx, "work_item_id", None) if ctx else None,
                "context_id": getattr(ctx, "context_id", None) if ctx else None,
            },
        )
    
    # Register routers
    app.include_router(health_router, tags=["health"])
    app.include_router(index_router)
    app.include_router(search_router)
    app.include_router(ref_router)
    app.include_router(mail_router)
    
    # Root endpoint
    @app.get("/")
    async def root() -> dict[str, str]:
        return {"service": "AutoHelper", "version": "0.1.0"}
    
    return app
