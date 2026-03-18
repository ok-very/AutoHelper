"""
Application factory - builds FastAPI app with all middleware and routes.
Pattern mirrors AutoArt's buildApp().
"""

from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from autohelper.config import Settings, get_settings
from autohelper.db import get_db, init_db
from autohelper.db.migrate import get_migration_status, run_migrations
from autohelper.modules.config.router import router as config_router
from autohelper.modules.contacts.router import router as contacts_router
from autohelper.modules.clickup.scheduler import start_clickup_scheduler, stop_clickup_scheduler
from autohelper.modules.contacts.scheduler import start_contact_scheduler, stop_contact_scheduler
from autohelper.modules.invoice_watch.router import router as invoice_watch_router
from autohelper.modules.pairing.router import router as pairing_router
from autohelper.modules.export.router import router as export_router
from autohelper.modules.file_watch.router import router as file_watch_router
from autohelper.modules.filetree.router import router as filetree_router
from autohelper.modules.gc.router import router as gc_router
from autohelper.modules.gc.scheduler import start_gc_scheduler, stop_gc_scheduler
from autohelper.gui.dashboard_router import (
    router as dashboard_router,
    get_static_files,
    get_artists_static_files,
    get_manifests_static_files,
)
from autohelper.modules.artists.router import router as artists_router
from autohelper.modules.clickup.router import router as clickup_router
from autohelper.modules.felt.router import router as felt_router
from autohelper.modules.documents.router import router as documents_router
from autohelper.modules.integrations.router import router as integrations_router
from autohelper.modules.integrations.oauth import router as oauth_router
from autohelper.modules.images.router import router as images_router
from autohelper.modules.projects.router import router as projects_router
from autohelper.modules.bfa_todo.router import router as bfa_todo_router
from autohelper.sync import start_backend_poller, stop_backend_poller

# Import routers
from autohelper.modules.health.router import router as health_router
from autohelper.modules.index.router import router as index_router
from autohelper.modules.mail.router import router as mail_router
from autohelper.modules.reference.router import router as ref_router
from autohelper.modules.runner.router import router as runner_router
from autohelper.modules.search.router import router as search_router
from autohelper.shared.errors import AutoHelperError
from autohelper.shared.ids import generate_request_id
from autohelper.shared.logging import (
    clear_request_context,
    get_logger,
    get_request_context,
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

    from autohelper.shared.platform import platform_label
    logger.info("Starting AutoHelper on %s...", platform_label())

    # Initialize database
    db = init_db(settings.db_path)
    logger.info(f"Database: {settings.db_path}")

    # Run migrations
    applied = run_migrations(db)
    if applied:
        logger.info(f"Applied {len(applied)} migrations")

    mig_status = get_migration_status(db)
    logger.info("Database: %d applied, %d pending", mig_status["applied_count"], mig_status["pending_count"])

    logger.info("AutoHelper started")

    # Start Mail Service
    from autohelper.modules.mail import MailService

    MailService().start()

    # Start GC Scheduler
    start_gc_scheduler()

    # Start Contact Sync Scheduler
    start_contact_scheduler()

    # Start ClickUp Template Sync Scheduler
    start_clickup_scheduler()

    # Start Backend Poller (syncs settings with AutoArt backend)
    start_backend_poller()

    # Start Artist File Watcher (if configured)
    if settings.artist_scan_enabled and settings.artist_scan_on_change and settings.artist_storage_root:
        from autohelper.modules.artists.watcher import get_artist_watcher

        watcher = get_artist_watcher()
        if watcher.start(settings.artist_storage_root):
            logger.info("Artist file watcher active")

    yield

    # Shutdown
    logger.info("Shutting down AutoHelper...")
    stop_backend_poller()
    stop_clickup_scheduler()
    stop_contact_scheduler()
    stop_gc_scheduler()
    MailService().stop()

    # Stop invoice watchers
    from autohelper.modules.invoice_watch.router import get_service as get_invoice_watch_service

    get_invoice_watch_service().shutdown()

    # Stop file watchers
    from autohelper.modules.file_watch.router import get_service as get_file_watch_service

    get_file_watch_service().shutdown()

    # Stop artist watcher
    from autohelper.modules.artists.watcher import get_artist_watcher

    get_artist_watcher().stop()

    # Shutdown shared filesystem event bus (stops any remaining Observers)
    from autohelper.shared.fs_events import get_event_bus

    get_event_bus().shutdown()

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
    async def request_context_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
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
    async def autohelper_error_handler(request: Request, exc: AutoHelperError) -> JSONResponse:
        """Handle AutoHelperError with consistent JSON response."""
        ctx = get_request_context()

        return JSONResponse(
            status_code=exc.http_status,
            content={
                "error": exc.to_dict(),
                "request_id": ctx.request_id if ctx else None,
                "work_item_id": ctx.work_item_id if ctx else None,
                "context_id": ctx.context_id if ctx else None,
            },
        )

    # Register routers
    app.include_router(health_router, tags=["health"])
    app.include_router(index_router)
    app.include_router(search_router)
    app.include_router(ref_router)
    app.include_router(mail_router)
    app.include_router(filetree_router)
    app.include_router(export_router)
    app.include_router(runner_router)
    app.include_router(gc_router)
    app.include_router(config_router)
    app.include_router(pairing_router)
    app.include_router(contacts_router)
    app.include_router(invoice_watch_router)
    app.include_router(file_watch_router)
    app.include_router(artists_router)
    app.include_router(clickup_router)
    app.include_router(felt_router)
    app.include_router(integrations_router)
    app.include_router(oauth_router, prefix="/api")
    app.include_router(documents_router)
    app.include_router(images_router)
    app.include_router(projects_router)
    app.include_router(bfa_todo_router)
    app.include_router(dashboard_router)

    # Mount dashboard static assets (JS, CSS)
    app.mount("/dashboard/static", get_static_files(), name="dashboard-static")
    app.mount("/artists-dashboard/static", get_artists_static_files(), name="artists-static")

    # Mount manifests directory for review engine
    manifests_static = get_manifests_static_files()
    if manifests_static:
        app.mount("/manifests", manifests_static, name="manifests-static")

    return app
