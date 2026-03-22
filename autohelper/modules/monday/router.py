"""Monday.com import REST endpoints."""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/monday", tags=["monday"])


@router.get("/boards")
async def list_boards() -> list[dict[str, Any]]:
    """List all active Monday.com project boards."""
    from .fetcher import fetch_board_list
    from .importer import _get_monday_client

    try:
        client = _get_monday_client()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return fetch_board_list(client)


@router.get("/overview")
async def list_overview_projects() -> list[dict[str, Any]]:
    """List all projects from the Current Projects Overview board, mapped."""
    from .fetcher import fetch_overview_rows
    from .importer import _get_monday_client
    from .mapper import overview_row_to_project

    try:
        client = _get_monday_client()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    rows = fetch_overview_rows(client)
    return [overview_row_to_project(row) for row in rows]


@router.get("/boards/{board_id}/preview")
async def preview_board(board_id: str) -> dict[str, Any]:
    """Dry-run preview: fetch board, show mapping, phase, contacts."""
    from .importer import preview_board as _preview

    try:
        return await _preview(board_id)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("Preview failed for board %s: %s", board_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/boards/{board_id}/import")
async def import_board(board_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Import a single Monday board into the full pipeline."""
    from .importer import import_board as _import

    municipality = body.get("municipality")
    if not municipality:
        raise HTTPException(status_code=400, detail="municipality is required")
    phase = body.get("phase", "")

    try:
        result = await _import(board_id, municipality, phase=phase)
        return asdict(result)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("Import failed for board %s: %s", board_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import-batch")
async def import_batch(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Import multiple boards. Body: {boards: [{id, municipality}, ...]}"""
    from .importer import import_batch as _batch

    boards = body.get("boards", [])
    if not boards:
        raise HTTPException(status_code=400, detail="boards list is required")

    for entry in boards:
        if not entry.get("id") or not entry.get("municipality"):
            raise HTTPException(status_code=400, detail="Each board needs id and municipality")

    results = await _batch(boards)
    return [asdict(r) for r in results]
