"""Dashboard router - serves the landing page, module pages, and settings."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, RedirectResponse
from starlette.staticfiles import StaticFiles

DASHBOARD_DIR = Path(__file__).parent / "dashboard"
ARTISTS_DIR = Path(__file__).parent / "artists"
ARTISTS_DIST_DIR = Path(__file__).parent / "artists-dist"
MANIFESTS_DIR = Path(__file__).parent / "manifests"

# Prefer Vite-built artists-dist/ when it exists, fall back to vanilla JS
_ARTISTS_SERVE = ARTISTS_DIST_DIR if ARTISTS_DIST_DIR.is_dir() else ARTISTS_DIR

# Vite outputs directory.html; vanilla JS uses index.html
_DIR_HTML = "directory.html" if _ARTISTS_SERVE == ARTISTS_DIST_DIR else "index.html"

# Prevent bfcache / stale HTML on navigation
_NO_CACHE = {"Cache-Control": "no-store"}

router = APIRouter()


# ── Landing page ──────────────────────────────────────────────────
@router.get("/", include_in_schema=False)
async def home_page() -> FileResponse:
    """Serve the landing page."""
    return FileResponse(_ARTISTS_SERVE / "home.html", media_type="text/html", headers=_NO_CACHE)


# ── System Settings (React) ──────────────────────────────────────
@router.get("/system-settings", include_in_schema=False)
async def system_settings() -> FileResponse:
    return FileResponse(_ARTISTS_SERVE / "system-settings.html", media_type="text/html", headers=_NO_CACHE)


# ── Global settings (legacy dashboard) ───────────────────────────
@router.get("/dashboard", include_in_schema=False)
async def dashboard_index() -> RedirectResponse:
    """Redirect legacy dashboard to system-settings."""
    return RedirectResponse("/system-settings", status_code=302)


# ── Artist Directory module ──────────────────────────────────────
@router.get("/artist-directory", include_in_schema=False)
async def artist_directory() -> FileResponse:
    return FileResponse(_ARTISTS_SERVE / _DIR_HTML, media_type="text/html", headers=_NO_CACHE)


@router.get("/artist-directory/health", include_in_schema=False)
async def artist_health() -> FileResponse:
    return FileResponse(_ARTISTS_SERVE / "health.html", media_type="text/html", headers=_NO_CACHE)


@router.get("/artist-directory/recon", include_in_schema=False)
async def artist_recon() -> FileResponse:
    return FileResponse(_ARTISTS_SERVE / "recon.html", media_type="text/html", headers=_NO_CACHE)


@router.get("/artist-directory/settings", include_in_schema=False)
async def artist_settings() -> FileResponse:
    return FileResponse(_ARTISTS_SERVE / "settings.html", media_type="text/html", headers=_NO_CACHE)


# ── Image Sorting module ─────────────────────────────────────────
@router.get("/image-sorting", include_in_schema=False)
async def image_sorting() -> FileResponse:
    return FileResponse(_ARTISTS_SERVE / "submissions.html", media_type="text/html", headers=_NO_CACHE)


@router.get("/image-sorting/settings", include_in_schema=False)
async def image_sorting_settings() -> FileResponse:
    return FileResponse(_ARTISTS_SERVE / "submissions-settings.html", media_type="text/html", headers=_NO_CACHE)


# ── Placeholder modules ──────────────────────────────────────────
@router.get("/art-collector", include_in_schema=False)
async def art_collector() -> FileResponse:
    return FileResponse(_ARTISTS_SERVE / "art-collector.html", media_type="text/html", headers=_NO_CACHE)


# ── Contacts module ──────────────────────────────────────────────
@router.get("/contacts", include_in_schema=False)
async def contacts_page() -> FileResponse:
    return FileResponse(_ARTISTS_SERVE / "contacts.html", media_type="text/html", headers=_NO_CACHE)


@router.get("/contacts/settings", include_in_schema=False)
async def contacts_settings() -> FileResponse:
    return FileResponse(_ARTISTS_SERVE / "contacts-settings.html", media_type="text/html", headers=_NO_CACHE)


# ── Mail module ─────────────────────────────────────────────────
@router.get("/mail", include_in_schema=False)
async def mail_page() -> FileResponse:
    return FileResponse(_ARTISTS_SERVE / "mail.html", media_type="text/html", headers=_NO_CACHE)


@router.get("/mail/settings", include_in_schema=False)
async def mail_settings() -> FileResponse:
    return FileResponse(_ARTISTS_SERVE / "mail-settings.html", media_type="text/html", headers=_NO_CACHE)


# ── Projects module ──────────────────────────────────────────────
@router.get("/projects", include_in_schema=False)
async def projects_page() -> FileResponse:
    return FileResponse(_ARTISTS_SERVE / "projects.html", media_type="text/html", headers=_NO_CACHE)


@router.get("/projects/new", include_in_schema=False)
async def projects_new() -> FileResponse:
    return FileResponse(_ARTISTS_SERVE / "projects-new.html", media_type="text/html", headers=_NO_CACHE)


@router.get("/projects/{project_id}", include_in_schema=False)
async def projects_detail(project_id: str) -> FileResponse:
    return FileResponse(_ARTISTS_SERVE / "projects-detail.html", media_type="text/html", headers=_NO_CACHE)


@router.get("/systems/policy-matrix", include_in_schema=False)
async def system_policy_matrix() -> FileResponse:
    return FileResponse(_ARTISTS_SERVE / "system-policy-matrix.html", media_type="text/html", headers=_NO_CACHE)


@router.get("/systems/email-templates", include_in_schema=False)
async def system_email_templates() -> FileResponse:
    return FileResponse(_ARTISTS_SERVE / "system-email-templates.html", media_type="text/html", headers=_NO_CACHE)


@router.get("/bfa-todo", include_in_schema=False)
async def bfa_todo() -> FileResponse:
    return FileResponse(_ARTISTS_SERVE / "bfa-todo.html", media_type="text/html", headers=_NO_CACHE)


@router.get("/analytics", include_in_schema=False)
async def analytics() -> FileResponse:
    return FileResponse(_ARTISTS_SERVE / "analytics.html", media_type="text/html", headers=_NO_CACHE)


# ── Legacy redirects (old bookmarks) ─────────────────────────────
@router.get("/artists-dashboard", include_in_schema=False)
async def legacy_artists_dashboard() -> RedirectResponse:
    return RedirectResponse("/artist-directory", status_code=302)


@router.get("/artists-settings", include_in_schema=False)
async def legacy_artists_settings() -> RedirectResponse:
    return RedirectResponse("/artist-directory/settings", status_code=302)


@router.get("/artists-health", include_in_schema=False)
async def legacy_artists_health() -> RedirectResponse:
    return RedirectResponse("/artist-directory/health", status_code=302)


@router.get("/artists-recon", include_in_schema=False)
async def legacy_artists_recon() -> RedirectResponse:
    return RedirectResponse("/artist-directory/recon", status_code=302)


@router.get("/client-directory", include_in_schema=False)
async def legacy_client_directory() -> RedirectResponse:
    return RedirectResponse("/contacts", status_code=302)


@router.get("/submissions", include_in_schema=False)
async def legacy_submissions() -> RedirectResponse:
    return RedirectResponse("/image-sorting", status_code=302)


@router.get("/submissions-settings", include_in_schema=False)
async def legacy_submissions_settings() -> RedirectResponse:
    return RedirectResponse("/image-sorting/settings", status_code=302)


# ── Static file mounts ───────────────────────────────────────────
def get_static_files() -> StaticFiles:
    """Return StaticFiles mount for dashboard assets (JS, CSS)."""
    return StaticFiles(directory=str(DASHBOARD_DIR))


def get_artists_static_files() -> StaticFiles:
    """Return StaticFiles mount for artist dashboard assets."""
    return StaticFiles(directory=str(_ARTISTS_SERVE))


def get_manifests_static_files() -> StaticFiles | None:
    """Return StaticFiles mount for manifests directory, or None if it doesn't exist."""
    if MANIFESTS_DIR.is_dir():
        return StaticFiles(directory=str(MANIFESTS_DIR))
    return None
