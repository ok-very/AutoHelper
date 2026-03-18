"""Async wrapper around felt-python (sync library)."""

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any

import httpx

from autohelper.shared.logging import get_logger

logger = get_logger(__name__)


class FeltClient:
    """Async Felt API client wrapping felt-python's sync functions."""

    def __init__(self, token: str) -> None:
        self.token = token

    async def create_map(
        self,
        title: str,
        lat: float,
        lon: float,
        public_access: str = "private",
    ) -> dict[str, Any]:
        import felt_python

        result: dict[str, Any] = await asyncio.to_thread(
            felt_python.create_map,
            title=title,
            lat=lat,
            lon=lon,
            public_access=public_access,
            api_token=self.token,
        )
        logger.info("Created Felt map: %s (%s)", result.get("id"), title)
        return result

    async def upload_file(
        self,
        map_id: str,
        file_path: str,
        layer_name: str,
    ) -> dict[str, Any]:
        """Upload a file as a layer. Bypasses felt-python's broken S3 multipart."""
        # Step 1: Get presigned upload URL from Felt API
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://felt.com/api/v2/maps/{map_id}/upload",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                json={"name": layer_name},
                timeout=30.0,
            )
            resp.raise_for_status()
            presigned = resp.json()

        # Step 2: Upload file to S3 using presigned attributes
        with open(file_path, "rb") as f:
            file_bytes = f.read()

        fname = Path(file_path).name
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                presigned["url"],
                data=presigned["presigned_attributes"],
                files={"file": (fname, file_bytes, "application/octet-stream")},
                timeout=60.0,
            )
            resp.raise_for_status()

        logger.info("Uploaded layer '%s' to map %s", layer_name, map_id)
        return {
            "layer_id": presigned.get("layer_id", ""),
            "layer_group_id": presigned.get("layer_group_id", ""),
        }

    async def upload_geojson(
        self,
        map_id: str,
        geojson: dict[str, Any],
        layer_name: str,
    ) -> dict[str, Any]:
        """Upload a GeoJSON dict as a layer by writing to a temp file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".geojson", delete=False
        ) as f:
            json.dump(geojson, f)
            tmp_path = f.name

        try:
            return await self.upload_file(map_id, tmp_path, layer_name)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    async def update_layer_style(
        self,
        map_id: str,
        layer_id: str,
        style: dict[str, Any],
    ) -> dict[str, Any]:
        import felt_python

        result: dict[str, Any] = await asyncio.to_thread(
            felt_python.update_layer_style,
            map_id=map_id,
            layer_id=layer_id,
            style=style,
            api_token=self.token,
        )
        return result

    async def get_map(self, map_id: str) -> dict[str, Any]:
        import felt_python

        result: dict[str, Any] = await asyncio.to_thread(
            felt_python.get_map,
            map_id=map_id,
            api_token=self.token,
        )
        return result

    async def upsert_elements(
        self,
        map_id: str,
        geojson_fc: dict[str, Any],
    ) -> dict[str, Any]:
        """Add pin elements to a map via the REST API directly."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://felt.com/api/v2/maps/{map_id}/elements",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                json=geojson_fc,
                timeout=30.0,
            )
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            return result

    async def validate_token(self) -> dict[str, Any]:
        """Test the API token by fetching user/workspace info."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://felt.com/api/v2/user",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=15.0,
            )
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            return result
