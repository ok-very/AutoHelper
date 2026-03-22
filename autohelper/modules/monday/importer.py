"""Monday.com → AutoHelper import pipeline orchestrator."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .types import MondayBoardData

logger = logging.getLogger(__name__)


@dataclass
class ImportResult:
    board_id: str
    board_name: str
    project_record_id: str | None = None
    clickup_list_id: str | None = None
    bfa_entry_uid: str | None = None
    phase: str = "TBC"
    tasks_matched: int = 0
    tasks_completed: int = 0
    correspondence_posted: int = 0
    contacts_created: int = 0
    file_links_collected: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _get_monday_client():
    from autohelper.config.store import ConfigStore
    from autohelper.modules.context.monday import MondayClient

    config = ConfigStore().load()
    token = config.get("monday_token")
    if not token:
        raise RuntimeError("Monday.com not connected — authenticate via Settings")
    return MondayClient(token=token)


async def preview_board(board_id: str) -> dict[str, Any]:
    """Dry run — fetch board, map to intake, show what would be created."""
    from .fetcher import fetch_board_full
    from .mapper import (
        board_to_intake,
        collect_correspondence,
        collect_file_links,
        derive_phase,
        extract_pm_contact,
        match_items_to_template,
    )

    client = _get_monday_client()
    board = fetch_board_full(client, board_id)

    item_to_temp = match_items_to_template(board)
    phase = derive_phase(board)
    pm = extract_pm_contact(board)
    correspondence = collect_correspondence(board, item_to_temp)
    file_links = collect_file_links(board)

    # Count completed items
    completed_statuses = {"completed", "executed", "done"}
    completed_matched = sum(
        1 for item in board.items
        if item.id in item_to_temp and item.status.lower() in completed_statuses
    )

    # Build match detail for preview
    match_detail = []
    for item in board.items:
        temp_id = item_to_temp.get(item.id)
        if temp_id:
            match_detail.append({
                "monday_item": item.name,
                "group": item.group_title,
                "temp_id": temp_id,
                "status": item.status,
            })

    # Check for existing project (duplicate detection)
    from autohelper.modules.projects.store import get_project_store

    store = get_project_store()
    all_projects = store.list_all()
    project_name = f"{board.developer} - {board.project}" if board.project else board.name
    existing = next(
        (p for p in all_projects if p.project_name.lower() == project_name.lower()),
        None,
    )

    return {
        "board_id": board.id,
        "board_name": board.name,
        "developer": board.developer,
        "project": board.project,
        "total_items": len(board.items),
        "tasks_matched": len(item_to_temp),
        "tasks_completed": completed_matched,
        "phase": phase,
        "pm": pm,
        "correspondence_count": len(correspondence),
        "file_links_count": len(file_links),
        "match_detail": match_detail,
        "intake_preview": board_to_intake(board, "(select municipality)"),
        "existing_project": {
            "id": existing.id,
            "status": existing.status.value,
            "clickup_list_id": existing.clickup_list_id,
            "municipality": existing.municipality,
        } if existing else None,
    }


async def import_board(
    board_id: str,
    municipality: str,
    phase: str = "",
) -> ImportResult:
    """Full import pipeline: Monday → ProjectRecord → ClickUp → BFA → contacts.

    Args:
        board_id: Monday project board ID
        municipality: City ID (e.g., "burnaby")
        phase: BFA phase from overview board (source of truth). Falls back to
               derivation from task completion if not provided.
    """
    from autohelper.config import get_settings
    from autohelper.modules.clickup.client import ClickUp
    from autohelper.modules.projects.service import create_project, provision_project
    from autohelper.modules.projects.types import IntakeAnswers

    from .fetcher import fetch_board_full
    from .mapper import (
        board_to_intake,
        collect_correspondence,
        collect_file_links,
        derive_phase,
        extract_pm_contact,
        match_items_to_template,
    )

    result = ImportResult(board_id=board_id, board_name="")

    # 1. Fetch board data
    try:
        client = _get_monday_client()
        board = fetch_board_full(client, board_id)
        result.board_name = board.name
    except Exception as e:
        result.errors.append(f"Failed to fetch board: {e}")
        return result

    # 2. Match items to BFA template
    item_to_temp = match_items_to_template(board)
    result.tasks_matched = len(item_to_temp)

    # 3. Phase from overview (source of truth), fallback to derivation
    result.phase = phase or derive_phase(board)
    intake_dict = board_to_intake(board, municipality)

    # 4. Create ProjectRecord
    try:
        intake = IntakeAnswers(**intake_dict)
        project = create_project(intake)
        result.project_record_id = project.id
        logger.info("Created ProjectRecord %s for board %s", project.id, board.name)
    except Exception as e:
        result.errors.append(f"Failed to create project: {e}")
        return result

    # 5. Provision to ClickUp
    try:
        project = await provision_project(project.id)
        result.clickup_list_id = project.clickup_list_id
        logger.info("Provisioned to ClickUp list %s", project.clickup_list_id)
    except Exception as e:
        result.errors.append(f"Provisioning failed: {e}")
        return result

    id_map = project.clickup_task_id_map or {}

    # 6. Post-provision wiring
    settings = get_settings()
    token = getattr(settings, "clickup_token", "")
    if token and id_map:
        try:
            async with ClickUp(token) as cu:
                completed_statuses = {"completed", "executed", "done"}

                # 6a. Mark completed tasks — stage-level logic
                # If all Monday items in a group/stage are complete,
                # close ALL ClickUp tasks at that stage (not just matched ones)
                from .mapper import _infer_bfa_stage

                # Build stage → completion status
                stage_items: dict[int, list[str]] = {}  # stage → [status, ...]
                for item in board.items:
                    stage = _infer_bfa_stage(item.group_title)
                    if stage is not None:
                        stage_items.setdefault(stage, []).append(item.status.lower())

                completed_stages: set[int] = set()
                for stage, statuses in stage_items.items():
                    if statuses and all(s in completed_statuses for s in statuses):
                        completed_stages.add(stage)

                # Load template tasks to know which temp_ids belong to each stage
                from .mapper import _load_template_tasks
                template_tasks = _load_template_tasks()
                temp_ids_by_stage: dict[int, list[str]] = {}
                for t in template_tasks:
                    s = t.get("stage", 0)
                    temp_ids_by_stage.setdefault(s, []).append(t["temp_id"])

                # Close all ClickUp tasks in completed stages
                for stage in completed_stages:
                    for temp_id in temp_ids_by_stage.get(stage, []):
                        clickup_id = id_map.get(temp_id)
                        if not clickup_id:
                            continue
                        try:
                            await cu.client.put(
                                f"/task/{clickup_id}",
                                body={"status": "complete"},
                            )
                            result.tasks_completed += 1
                        except Exception as e:
                            result.warnings.append(f"Failed to close task {temp_id}: {e}")

                # 6b. Post correspondence as comments
                correspondence = collect_correspondence(board, item_to_temp)
                for corr in correspondence:
                    clickup_task_id = id_map.get(corr.temp_id)
                    if not clickup_task_id:
                        continue
                    # Format comment with metadata
                    prefix = ""
                    if corr.source == "email_template":
                        prefix = "[Email Template]\n\n"
                    elif corr.creator:
                        prefix = f"[{corr.creator}"
                        if corr.created_at:
                            prefix += f" — {corr.created_at[:10]}"
                        prefix += "]\n\n"

                    comment_text = prefix + corr.content
                    try:
                        await cu.client.post(
                            f"/task/{clickup_task_id}/comment",
                            body={"comment_text": comment_text},
                        )
                        result.correspondence_posted += 1
                    except Exception as e:
                        result.warnings.append(
                            f"Failed to post comment on {corr.temp_id}: {e}"
                        )

        except Exception as e:
            result.errors.append(f"Post-provision wiring failed: {e}")

    # 7. Create BFA To Do entry
    try:
        from autohelper.modules.bfa_todo.clickup_sync import sync_from_clickup

        sync_result = await sync_from_clickup()
        # Find the entry created for this project
        # It gets linked by project_record_id during sync
        if sync_result:
            result.bfa_entry_uid = sync_result.get("created", [None])[0] if sync_result.get("created") else None
    except Exception as e:
        result.warnings.append(f"BFA sync failed: {e}")

    # 8. Extract PM → hub contact
    pm = extract_pm_contact(board)
    if pm and result.project_record_id:
        try:
            from autohelper.modules.contacts.hub import (
                associate_contact,
                create_contact,
                get_contact_by_email,
            )

            # Create or find contact (no email available from Monday people column)
            contact = create_contact(
                full_name=pm["full_name"],
                first_name=pm["first_name"],
                last_name=pm["last_name"],
                email_primary=f"{pm['first_name'].lower()}.{pm['last_name'].lower()}@ballardfineart.com",
                source="monday_import",
            )
            associate_contact(
                contact_id=contact.id,
                project_id=result.project_record_id,
                role="project_coordinator",
                notes="Imported from Monday.com PM column",
            )
            result.contacts_created += 1
        except Exception as e:
            result.warnings.append(f"PM contact creation failed: {e}")

    # 9. Collect file links
    file_links = collect_file_links(board)
    result.file_links_collected = len(file_links)
    # TODO: store file links on BFA entry or ProjectRecord

    return result


async def import_batch(
    boards: list[dict[str, str]],
) -> list[ImportResult]:
    """Import multiple boards. boards = [{id, municipality, phase?}, ...]"""
    results = []
    for entry in boards:
        board_id = entry["id"]
        municipality = entry["municipality"]
        phase = entry.get("phase", "")
        try:
            result = await import_board(board_id, municipality, phase=phase)
            results.append(result)
        except Exception as e:
            results.append(ImportResult(
                board_id=board_id,
                board_name=entry.get("name", ""),
                errors=[str(e)],
            ))
    return results
