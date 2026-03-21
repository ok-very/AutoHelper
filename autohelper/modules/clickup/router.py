"""FastAPI routes for ClickUp integration."""

from __future__ import annotations

import secrets
import time
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from .manifest import ImportManifest, ManifestExecutionResult
from .service import execute_manifest, validate_connection

router = APIRouter(prefix="/clickup", tags=["clickup"])

# ── OAuth state store (in-memory, 10-minute TTL) ─────────────────────────

_oauth_states: dict[str, float] = {}  # state -> expiry timestamp
_STATE_TTL = 600  # 10 minutes


@router.get("/auth")
async def clickup_auth() -> dict[str, Any]:
    """Initiate ClickUp OAuth flow — returns authorization URL."""
    from autohelper.config import get_settings

    settings = get_settings()
    client_id = getattr(settings, "clickup_client_id", "")
    redirect_uri = getattr(settings, "clickup_redirect_uri", "")

    if not client_id:
        raise HTTPException(
            status_code=400,
            detail="CLICKUP_CLIENT_ID not configured",
        )

    # Clean expired states
    now = time.time()
    expired = [k for k, v in _oauth_states.items() if v < now]
    for k in expired:
        del _oauth_states[k]

    state = secrets.token_urlsafe(32)
    _oauth_states[state] = now + _STATE_TTL

    url = f"https://app.clickup.com/api?client_id={client_id}&redirect_uri={redirect_uri}&state={state}"
    return {"url": url, "state": state}


@router.get("/callback", response_class=HTMLResponse)
async def clickup_callback(
    code: str = Query(...),
    state: str = Query(""),
) -> HTMLResponse:
    """Handle ClickUp OAuth callback — exchange code for token."""
    from autohelper.config import get_settings, reset_settings
    from autohelper.config.store import ConfigStore
    from autohelper.shared.logging import get_logger

    logger = get_logger(__name__)

    # Validate state (optional — ClickUp state param is advisory)
    if state:
        now = time.time()
        expiry = _oauth_states.pop(state, None)
        if expiry is not None and expiry < now:
            logger.warning("ClickUp OAuth state expired, proceeding anyway")

    settings = get_settings()
    client_id = getattr(settings, "clickup_client_id", "")
    client_secret = getattr(settings, "clickup_client_secret", "")

    if not client_id or not client_secret:
        return HTMLResponse(
            "<html><body><h2>Configuration error</h2>"
            "<p>ClickUp client credentials not configured.</p>"
            "<script>window.opener?.postMessage({type:'clickup-oauth',ok:false,error:'no_credentials'},'*');window.close()</script>"
            "</body></html>",
            status_code=500,
        )

    # Exchange code for access token
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.clickup.com/api/v2/oauth/token",
                params={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.error("ClickUp token exchange failed: %s", exc)
        return HTMLResponse(
            f"<html><body><h2>Token exchange failed</h2>"
            f"<p>{exc}</p>"
            f"<script>window.opener?.postMessage({{type:'clickup-oauth',ok:false,error:'token_exchange_failed'}},'*');window.close()</script>"
            f"</body></html>",
            status_code=502,
        )

    access_token = data.get("access_token")
    if not access_token:
        return HTMLResponse(
            "<html><body><h2>No access token received</h2>"
            "<script>window.opener?.postMessage({type:'clickup-oauth',ok:false,error:'no_token'},'*');window.close()</script>"
            "</body></html>",
            status_code=502,
        )

    # Persist token to config.json
    store = ConfigStore()
    cfg = store.load()
    cfg["clickup_token"] = access_token
    store.save(cfg)
    reset_settings()

    logger.info("ClickUp OAuth token acquired and saved")

    return HTMLResponse(
        "<html><body><h2>Connected to ClickUp</h2>"
        "<p>You can close this window.</p>"
        "<script>window.opener?.postMessage({type:'clickup-oauth',ok:true},'*');setTimeout(()=>window.close(),1000)</script>"
        "</body></html>"
    )


# ── Members cache ─────────────────────────────────────────────────────────

_members_cache: list[dict[str, Any]] | None = None
_members_cache_time: float = 0
_MEMBERS_TTL = 300  # 5 minutes


@router.get("/members")
async def clickup_members() -> list[dict[str, Any]]:
    """Return workspace members (cached 5min)."""
    global _members_cache, _members_cache_time

    now = time.time()
    if _members_cache is not None and now - _members_cache_time < _MEMBERS_TTL:
        return _members_cache

    from .service import _get_token
    from .client import ClickUp as CU

    try:
        token = _get_token()
        async with CU(token) as cu:
            teams = await cu.teams.list()

        members: dict[int, dict[str, Any]] = {}
        for team in teams:
            for m in team.members:
                u = m.user
                if u.id not in members:
                    members[u.id] = {
                        "id": u.id,
                        "username": u.username,
                        "initials": u.initials or "",
                        "email": u.email or "",
                    }

        _members_cache = list(members.values())
        _members_cache_time = now
        return _members_cache
    except Exception as e:
        raise HTTPException(500, f"Failed to fetch members: {e}")


@router.get("/validate")
async def clickup_validate() -> dict[str, Any]:
    """Validate ClickUp connection and return workspace info."""
    try:
        info = await validate_connection()
        return {
            "ok": True,
            "workspace": info["workspace_name"],
            "workspace_id": info["workspace_id"],
        }
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/execute-manifest", response_model=ManifestExecutionResult)
async def clickup_execute_manifest(
    manifest: ImportManifest,
) -> ManifestExecutionResult:
    """Execute an import manifest — create tasks in ClickUp."""
    try:
        return await execute_manifest(manifest)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# ── Template Sync ─────────────────────────────────────────────────────────


@router.post("/template-sync")
async def clickup_template_sync(
    force: bool = Query(False, description="Apply changes (default: dry-run)"),
    list_id: str | None = Query(None, description="Override list ID"),
) -> dict[str, Any]:
    """Run BFA template sync against ClickUp list."""
    from .template_sync import sync_template

    try:
        report = await sync_template(force=force, list_id=list_id)
        return {
            "applied": report.applied,
            "total_template": report.total_template,
            "total_clickup": report.total_clickup,
            "creates": len(report.creates),
            "updates": len(report.updates),
            "orphans": len(report.orphans),
            "errors": report.errors,
            "actions": [
                {
                    "action": a.action,
                    "name": a.name,
                    "temp_id": a.temp_id,
                    "details": a.details,
                }
                for a in report.creates + report.updates + report.orphans
            ],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/template-sync/status")
async def clickup_template_sync_status() -> dict[str, Any]:
    """Get template sync scheduler status."""
    from .scheduler import get_next_sync_time

    from autohelper.config import get_settings

    settings = get_settings()
    next_sync = get_next_sync_time()

    return {
        "enabled": getattr(settings, "clickup_sync_enabled", False),
        "interval_hours": getattr(settings, "clickup_sync_interval_hours", 6),
        "next_sync": next_sync.isoformat() if next_sync else None,
    }


# ── Project Status ────────────────────────────────────────────────────────


@router.get("/project-status")
async def clickup_project_status(
    list_id: str = Query(..., description="ClickUp list ID to analyze"),
    project_id: str | None = Query(None, description="Optional project ID — uses resolved template instead of base"),
) -> dict[str, Any]:
    """
    Analyze a BFA project list and return dependency-aware project state.

    Returns current stage, stage progress, actionable/blocked tasks,
    and the next milestone.

    If project_id is provided, uses that project's resolved template
    (with city overlay and conditions applied) instead of the base template.
    """
    import json
    from importlib import resources as pkg_resources

    from .client import ClickUp as CU
    from .service import _get_token

    try:
        token = _get_token()

        # Load template — resolved from project if project_id given, else base
        if project_id:
            from autohelper.modules.projects.service import get_project
            from autohelper.modules.projects.template_resolver import resolve_template

            project = get_project(project_id)
            if project is None:
                raise ValueError(f"Project {project_id} not found")
            manifest = resolve_template(project.intake)
            # Convert resolved manifest to template-compatible format
            template = {
                "stages": [{"number": s.number, "name": s.name} for s in manifest.stages],
                "tasks": [
                    {
                        "temp_id": t.temp_id,
                        "name": t.name,
                        "stage": t.stage,
                        "is_milestone": t.is_milestone,
                        "depends_on": t.depends_on,
                        "email_template_key": t.email_template_key,
                    }
                    for t in manifest.tasks
                ],
            }
        else:
            data_pkg = pkg_resources.files("autohelper") / "data" / "bfa_templates.json"
            template = json.loads(data_pkg.read_text(encoding="utf-8"))

        async with CU(token) as cu:
            # Fetch all tasks
            all_tasks = await cu.tasks.list_all(list_id, include_closed=True)

        # Build template lookups
        tmpl_by_name: dict[str, dict[str, Any]] = {}
        tmpl_by_id: dict[str, dict[str, Any]] = {}
        for t in template["tasks"]:
            tmpl_by_name[t["name"].strip().lower()] = t
            tmpl_by_id[t["temp_id"]] = t

        # Map ClickUp tasks to template
        temp_to_cu: dict[str, dict[str, Any]] = {}
        completed_temps: set[str] = set()
        done_types = {"closed", "done", "complete", "completed"}

        for task in all_tasks:
            tmpl = tmpl_by_name.get(task.name.strip().lower())
            if not tmpl:
                continue
            temp_to_cu[tmpl["temp_id"]] = {
                "id": task.id,
                "name": task.name,
                "status": task.status.status,
            }
            if task.status.type.lower() in done_types:
                completed_temps.add(tmpl["temp_id"])

        # Build reverse blocks map
        blocks_map: dict[str, list[str]] = {}
        for t in template["tasks"]:
            for dep in t.get("depends_on", []):
                blocks_map.setdefault(dep, []).append(t["temp_id"])

        # Classify tasks
        actionable: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
        completed_count = 0
        stage_progress: dict[int, dict[str, int]] = {}
        for s in template["stages"]:
            stage_progress[s["number"]] = {"total": 0, "done": 0}

        next_milestone: dict[str, Any] | None = None

        for tmpl in template["tasks"]:
            stage = tmpl["stage"]
            if stage in stage_progress:
                stage_progress[stage]["total"] += 1

            if tmpl["temp_id"] in completed_temps:
                completed_count += 1
                if stage in stage_progress:
                    stage_progress[stage]["done"] += 1
                continue

            unresolved = [
                d for d in tmpl.get("depends_on", []) if d not in completed_temps
            ]
            cu_task = temp_to_cu.get(tmpl["temp_id"])

            summary = {
                "id": cu_task["id"] if cu_task else tmpl["temp_id"],
                "name": tmpl["name"],
                "stage": stage,
                "status": cu_task["status"] if cu_task else "not created",
                "blockedBy": [
                    temp_to_cu[d]["id"]
                    for d in unresolved
                    if d in temp_to_cu
                ],
                "blocks": [
                    temp_to_cu[b]["id"]
                    for b in blocks_map.get(tmpl["temp_id"], [])
                    if b in temp_to_cu
                ],
                "hasEmailTemplate": bool(tmpl.get("email_template_key")),
                "isMilestone": tmpl.get("is_milestone", False),
            }

            if unresolved:
                blocked.append(summary)
            else:
                actionable.append(summary)

            if tmpl.get("is_milestone") and next_milestone is None:
                next_milestone = summary

        # Compute percentages
        stage_result: dict[str, dict[str, Any]] = {}
        for s in template["stages"]:
            sp = stage_progress[s["number"]]
            pct = round(sp["done"] / sp["total"] * 100) if sp["total"] > 0 else 0
            stage_result[str(s["number"])] = {
                "name": s["name"],
                "total": sp["total"],
                "done": sp["done"],
                "pct": pct,
            }

        # Current stage
        current_stage = template["stages"][-1]["number"]
        for s in template["stages"]:
            sp = stage_progress[s["number"]]
            if sp["done"] < sp["total"]:
                current_stage = s["number"]
                break

        stage_name = next(
            (s["name"] for s in template["stages"] if s["number"] == current_stage),
            f"Stage {current_stage}",
        )

        return {
            "currentStage": current_stage,
            "stageName": stage_name,
            "stageProgress": stage_result,
            "actionableTasks": actionable,
            "blockedTasks": blocked[:20],
            "nextMilestone": next_milestone,
            "completedCount": completed_count,
            "totalCount": len(template["tasks"]),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# ── Artist Sync ──────────────────────────────────────────────────────────


@router.post("/artist-sync")
async def clickup_artist_sync(
    list_id: str = Query("", description="ClickUp list ID for artist records"),
    dry_run: bool = Query(True, description="Preview only (default: true)"),
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Sync artist records to a ClickUp list."""
    from .artist_sync import sync_artists, _get_artist_list_id

    try:
        resolved_list_id = _get_artist_list_id(list_id or None)
        artist_ids = (body or {}).get("artist_ids")
        return await sync_artists(
            list_id=resolved_list_id,
            dry_run=dry_run,
            artist_ids=artist_ids,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# ── Email Compose ─────────────────────────────────────────────────────────


@router.post("/compose-email")
async def clickup_compose_email(
    task_id: str = Query(..., description="ClickUp task ID"),
    template_key: str = Query(..., description="Email template key (e.g. '01.1')"),
) -> dict[str, Any]:
    """
    Compose an email draft from a ClickUp task and email template.

    Fetches task data from ClickUp, merges with template, and creates
    an Outlook draft via COM or Graph API.
    """
    from .email_templates import TemplateRegistry
    from .service import _get_token
    from .client import ClickUp as CU

    try:
        registry = TemplateRegistry.load()
        template = registry.get(template_key)
        if not template:
            raise HTTPException(
                status_code=404,
                detail=f"Template '{template_key}' not found",
            )

        # Fetch task data from ClickUp
        token = _get_token()
        async with CU(token) as cu:
            task = await cu.tasks.get(task_id)

        # Build merge context from task custom fields
        context: dict[str, str] = {
            "project_name": "",
            "developer": "",
            "name": "",
            "your_name": "",
        }

        # Extract from task name or custom fields
        for cf in task.custom_fields:
            cf_name = cf.name.lower().strip()
            if "project" in cf_name and cf.value:
                context["project_name"] = str(cf.value)
            elif "developer" in cf_name and cf.value:
                context["developer"] = str(cf.value)

        # Merge template with context
        merged = registry.merge(template_key, context)
        if not merged:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to merge template '{template_key}'",
            )

        # Create Outlook draft
        from autohelper.modules.mail.draft import (
            can_use_outlook,
            create_draft_via_com,
        )

        if can_use_outlook():
            result = create_draft_via_com(
                to="",  # Left empty for PM to fill in
                subject=merged.subject,
                body=merged.html_body,
            )
            return {
                "status": "draft_created",
                "strategy": "outlook_com",
                "subject": merged.subject,
                **result,
            }

        return {
            "status": "preview",
            "subject": merged.subject,
            "html_body": merged.html_body,
            "merge_fields": list(context.keys()),
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
