"""
Runner module API router.
"""

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from autohelper.shared.logging import get_logger

from .lookup_service import get_lookup_service
from .service import get_runner_service
from .types import ArtifactManifestEntry, CollectionManifest, InvokeRequest, RunnerResult

logger = get_logger(__name__)

router = APIRouter(prefix="/runner", tags=["runner"])


@router.get("/status")
async def get_status() -> dict[str, Any]:
    """Get status of the runner system and available runners."""
    service = get_runner_service()
    status = service.get_status()

    return {
        "status": "ok",
        "runners": service.list_runners(),
        "active": status.active,
        "current_runner": status.current_runner.value if status.current_runner else None,
        "progress": status.progress.model_dump() if status.progress else None,
    }


@router.post("/invoke")
async def invoke_runner(request: InvokeRequest) -> RunnerResult:
    """
    Invoke a runner synchronously.

    Returns the result once the runner completes.
    """
    logger.info(f"Invoking runner: {request.runner_id}")

    service = get_runner_service()
    result = await service.invoke(request)

    if not result.success:
        logger.warning(f"Runner {request.runner_id} failed: {result.error}")
    else:
        logger.info(f"Runner {request.runner_id} completed: {len(result.artifacts)} artifacts")

    return result


@router.post("/invoke/stream")
async def invoke_runner_stream(request: InvokeRequest) -> StreamingResponse:
    """
    Invoke a runner and stream progress updates via SSE.

    Streams Server-Sent Events with progress updates until completion.
    """
    logger.info(f"Streaming runner: {request.runner_id}")

    service = get_runner_service()

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            async for progress in service.invoke_stream(request):
                try:
                    # Format as SSE
                    data = json.dumps(progress.model_dump())
                    yield f"data: {data}\n\n"
                except (TypeError, ValueError) as e:
                    # Handle JSON serialization errors
                    logger.warning(f"Failed to serialize progress: {e}")
                    error_data = json.dumps(
                        {
                            "stage": "error",
                            "message": f"Serialization error: {str(e)}",
                            "percent": None,
                        }
                    )
                    yield f"data: {error_data}\n\n"
        except Exception as e:
            # Handle unexpected errors during streaming
            logger.exception(f"Error during streaming: {e}")
            error_data = json.dumps(
                {
                    "stage": "error",
                    "message": f"Stream error: {str(e)}",
                    "percent": None,
                }
            )
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# =============================================================================
# Artifact Lookup Endpoints
# =============================================================================


class ArtifactResponse(BaseModel):
    """Response for single artifact lookup."""

    found: bool
    artifact: ArtifactManifestEntry | None = None


class ArtifactListResponse(BaseModel):
    """Response for multiple artifact lookup."""

    count: int
    artifacts: list[ArtifactManifestEntry]


class CollectionListResponse(BaseModel):
    """Response for collection listing."""

    count: int
    collections: list[dict[str, Any]]


class CollectionResponse(BaseModel):
    """Response for single collection lookup."""

    found: bool
    collection: CollectionManifest | None = None


class UpdateLocationRequest(BaseModel):
    """Request to update artifact location."""

    artifact_id: str
    new_path: str
    output_folder: str


@router.get("/artifacts/{artifact_id}")
async def get_artifact_by_id(
    artifact_id: str,
    output_folder: str | None = Query(None, description="Specific folder to search"),
) -> ArtifactResponse:
    """
    Look up an artifact by its persistent ID.

    The artifact ID is stable across file moves and renames.
    If output_folder is provided, only searches that folder's manifest.
    Otherwise, searches the database for all known collections.
    """
    service = get_lookup_service()
    artifact = await service.find_artifact_by_id(artifact_id, output_folder)

    return ArtifactResponse(
        found=artifact is not None,
        artifact=artifact,
    )


@router.get("/artifacts/hash/{content_hash}")
async def get_artifacts_by_hash(
    content_hash: str,
    output_folder: str | None = Query(None, description="Specific folder to search"),
) -> ArtifactListResponse:
    """
    Find artifacts by content hash.

    Useful for finding files that have been moved or renamed.
    The content hash is a SHA-256 hash of the file contents.
    """
    service = get_lookup_service()
    artifacts = await service.find_artifacts_by_hash(content_hash, output_folder)

    return ArtifactListResponse(
        count=len(artifacts),
        artifacts=artifacts,
    )


@router.get("/collections")
async def list_collections(
    output_folder: str | None = Query(None, description="Filter to specific folder"),
) -> CollectionListResponse:
    """
    List all artifact collections.

    Returns summaries of all active collections with their metadata.
    """
    service = get_lookup_service()
    collections = await service.list_collections(output_folder)

    return CollectionListResponse(
        count=len(collections),
        collections=collections,
    )


@router.get("/collections/{collection_id}")
async def get_collection(collection_id: str) -> CollectionResponse:
    """
    Get a full collection manifest by ID.

    Returns the complete manifest including all artifact entries.
    """
    service = get_lookup_service()
    collection = await service.get_collection(collection_id)

    return CollectionResponse(
        found=collection is not None,
        collection=collection,
    )


@router.post("/artifacts/update-location")
async def update_artifact_location(request: UpdateLocationRequest) -> dict[str, Any]:
    """
    Update an artifact's location after file move.

    Updates both the manifest and database with the new path.
    """
    service = get_lookup_service()

    try:
        success = await service.update_artifact_location(
            artifact_id=request.artifact_id,
            new_path=request.new_path,
            output_folder=request.output_folder,
        )

        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Artifact {request.artifact_id} not found",
            )

        return {
            "success": True,
            "artifact_id": request.artifact_id,
            "new_path": request.new_path,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception(f"Failed to update artifact location: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/artifacts/compute-hash")
async def compute_file_hash(
    file_path: str = Query(..., description="Path to file to hash"),
) -> dict[str, str]:
    """
    Compute SHA-256 hash of a file.

    Useful for finding moved files by their content hash.
    File must be within allowed roots configured in settings.
    """
    from pathlib import Path

    from autohelper.config.settings import get_settings

    # Offload blocking Path operations to threadpool
    def _validate_path() -> tuple[Path, str | None]:
        """Validate path and return (resolved_path, error_message)."""
        path = Path(file_path).resolve()

        settings = get_settings()
        allowed_roots = settings.get_allowed_roots()
        is_allowed = any(path == root or path.is_relative_to(root) for root in allowed_roots)
        if not is_allowed:
            return path, "forbidden"

        if not path.exists():
            return path, "not_found"

        if not path.is_file():
            return path, "not_file"

        return path, None

    path, error = await asyncio.to_thread(_validate_path)

    if error == "forbidden":
        raise HTTPException(
            status_code=403,
            detail="Access denied: path is not within allowed directories",
        )
    elif error == "not_found":
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    elif error == "not_file":
        raise HTTPException(status_code=400, detail=f"Path is not a file: {file_path}")

    service = get_lookup_service()
    # Use resolved path to ensure consistent handling
    content_hash = await service.compute_file_hash(str(path))

    return {
        "file_path": str(path),
        "content_hash": content_hash,
    }
