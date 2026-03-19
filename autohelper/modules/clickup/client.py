"""
ClickUp REST API client.

Low-level HTTP wrapper with rate-limit retry and typed responses.
Mirrors the TS client in packages/clickup/src/client.ts.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from .types import (
    ClickUpCustomField,
    ClickUpFolder,
    ClickUpList,
    ClickUpSpace,
    ClickUpTask,
    ClickUpTeam,
    CreateTaskData,
    FieldsResponse,
    FoldersResponse,
    ListsResponse,
    SpacesResponse,
    TasksResponse,
    TeamsResponse,
    UpdateTaskData,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://api.clickup.com/api/v2"
RATE_LIMIT_DELAY = 1.5  # seconds


class ClickUpApiError(Exception):
    """ClickUp API error with status code and response body."""

    def __init__(self, message: str, status_code: int, body: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class ClickUpClient:
    """Low-level async HTTP client for ClickUp API v2."""

    def __init__(
        self,
        token: str,
        base_url: str = BASE_URL,
        max_retries: int = 3,
    ) -> None:
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self._client: httpx.AsyncClient | None = None

    @staticmethod
    def _auth_header(token: str) -> str:
        """Return the correct Authorization header value for the token type."""
        # Personal API tokens start with pk_, OAuth tokens do not
        if token.startswith("pk_"):
            return token
        return f"Bearer {token}"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={
                    "Authorization": self._auth_header(self.token),
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
    ) -> Any:
        """Make HTTP request with rate-limit retry."""
        client = await self._get_client()
        url = f"{self.base_url}{path}"

        # Filter None values from query params
        params: dict[str, str] | None = None
        if query:
            params = {k: str(v) for k, v in query.items() if v is not None}

        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = await client.request(
                    method,
                    url,
                    json=body,
                    params=params,
                )
            except httpx.RequestError as e:
                raise ClickUpApiError(f"Request failed: {e}", 0) from e

            # Rate limited — wait and retry
            if response.status_code == 429:
                retry_after = response.headers.get("retry-after")
                delay = (
                    float(retry_after)
                    if retry_after
                    else RATE_LIMIT_DELAY * (attempt + 1)
                )
                logger.warning(
                    "ClickUp rate limited, retrying in %.1fs (attempt %d/%d)",
                    delay,
                    attempt + 1,
                    self.max_retries,
                )
                await asyncio.sleep(delay)
                last_error = ClickUpApiError("Rate limited", 429)
                continue

            if response.status_code >= 400:
                text = response.text
                try:
                    parsed = response.json()
                except Exception:
                    parsed = text
                raise ClickUpApiError(
                    f"ClickUp API {method} {path} failed: {response.status_code}",
                    response.status_code,
                    parsed,
                )

            # 204 No Content
            if response.status_code == 204:
                return None

            return response.json()

        raise last_error or ClickUpApiError("Max retries exceeded", 429)

    async def get(self, path: str, query: dict[str, Any] | None = None) -> Any:
        return await self.request("GET", path, query=query)

    async def post(
        self,
        path: str,
        body: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
    ) -> Any:
        return await self.request("POST", path, body=body, query=query)

    async def put(
        self,
        path: str,
        body: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
    ) -> Any:
        return await self.request("PUT", path, body=body, query=query)

    async def delete(self, path: str, query: dict[str, Any] | None = None) -> Any:
        return await self.request("DELETE", path, query=query)


# ── High-Level API ────────────────────────────────────────────────────────


class TasksAPI:
    """High-level task operations."""

    def __init__(self, client: ClickUpClient) -> None:
        self._client = client

    async def create(self, list_id: str, data: CreateTaskData) -> ClickUpTask:
        body = data.model_dump(exclude_none=True)
        result = await self._client.post(f"/list/{list_id}/task", body=body)
        return ClickUpTask.model_validate(result)

    async def get(self, task_id: str) -> ClickUpTask:
        result = await self._client.get(f"/task/{task_id}")
        return ClickUpTask.model_validate(result)

    async def update(self, task_id: str, data: UpdateTaskData) -> ClickUpTask:
        body = data.model_dump(exclude_none=True)
        result = await self._client.put(f"/task/{task_id}", body=body)
        return ClickUpTask.model_validate(result)

    async def list(
        self,
        list_id: str,
        *,
        archived: bool = False,
        page: int = 0,
        subtasks: bool = True,
        include_closed: bool = False,
    ) -> TasksResponse:
        result = await self._client.get(
            f"/list/{list_id}/task",
            query={
                "archived": str(archived).lower(),
                "page": page,
                "subtasks": str(subtasks).lower(),
                "include_closed": str(include_closed).lower(),
            },
        )
        return TasksResponse.model_validate(result)

    async def list_all(
        self,
        list_id: str,
        *,
        archived: bool = False,
        subtasks: bool = True,
        include_closed: bool = False,
    ) -> list[ClickUpTask]:
        """Fetch all tasks across all pages."""
        all_tasks: list[ClickUpTask] = []
        page = 0
        while True:
            resp = await self.list(
                list_id,
                archived=archived,
                page=page,
                subtasks=subtasks,
                include_closed=include_closed,
            )
            all_tasks.extend(resp.tasks)
            if resp.last_page:
                break
            page += 1
        return all_tasks


class CommentsAPI:
    """Task comment operations."""

    def __init__(self, client: ClickUpClient) -> None:
        self._client = client

    async def create(
        self, task_id: str, comment_text: str, *, notify_all: bool = False
    ) -> dict[str, Any]:
        """Post a comment to a ClickUp task."""
        result = await self._client.post(
            f"/task/{task_id}/comment",
            body={"comment_text": comment_text, "notify_all": notify_all},
        )
        return result


class ListsAPI:
    """High-level list operations."""

    def __init__(self, client: ClickUpClient) -> None:
        self._client = client

    async def create(self, folder_id: str, name: str, **kwargs: Any) -> ClickUpList:
        body: dict[str, Any] = {"name": name, **kwargs}
        result = await self._client.post(f"/folder/{folder_id}/list", body=body)
        return ClickUpList.model_validate(result)

    async def get(self, list_id: str) -> ClickUpList:
        result = await self._client.get(f"/list/{list_id}")
        return ClickUpList.model_validate(result)

    async def get_fields(self, list_id: str) -> list[ClickUpCustomField]:
        result = await self._client.get(f"/list/{list_id}/field")
        resp = FieldsResponse.model_validate(result)
        return resp.fields


class SpacesAPI:
    """High-level space operations."""

    def __init__(self, client: ClickUpClient) -> None:
        self._client = client

    async def list(self, team_id: str) -> list[ClickUpSpace]:
        result = await self._client.get(f"/team/{team_id}/space")
        resp = SpacesResponse.model_validate(result)
        return resp.spaces

    async def get(self, space_id: str) -> ClickUpSpace:
        result = await self._client.get(f"/space/{space_id}")
        return ClickUpSpace.model_validate(result)

    async def get_folders(self, space_id: str) -> list[ClickUpFolder]:
        result = await self._client.get(f"/space/{space_id}/folder")
        resp = FoldersResponse.model_validate(result)
        return resp.folders

    async def get_folderless_lists(self, space_id: str) -> list[ClickUpList]:
        result = await self._client.get(f"/space/{space_id}/list")
        resp = ListsResponse.model_validate(result)
        return resp.lists


class CustomFieldsAPI:
    """High-level custom field operations."""

    def __init__(self, client: ClickUpClient) -> None:
        self._client = client

    async def set(self, task_id: str, field_id: str, value: Any) -> None:
        await self._client.post(
            f"/task/{task_id}/field/{field_id}",
            body={"value": value},
        )


class TeamsAPI:
    """High-level workspace/team operations."""

    def __init__(self, client: ClickUpClient) -> None:
        self._client = client

    async def list(self) -> list[ClickUpTeam]:
        result = await self._client.get("/team")
        resp = TeamsResponse.model_validate(result)
        return resp.teams


class ClickUp:
    """
    High-level ClickUp API client.

    Usage:
        cu = ClickUp(token="pk_...")
        teams = await cu.teams.list()
        task = await cu.tasks.create(list_id, CreateTaskData(name="My Task"))
        await cu.custom_fields.set(task.id, field_id, "value")
        await cu.close()
    """

    def __init__(
        self,
        token: str,
        base_url: str = BASE_URL,
        max_retries: int = 3,
    ) -> None:
        self.client = ClickUpClient(token, base_url, max_retries)
        self.tasks = TasksAPI(self.client)
        self.lists = ListsAPI(self.client)
        self.spaces = SpacesAPI(self.client)
        self.custom_fields = CustomFieldsAPI(self.client)
        self.comments = CommentsAPI(self.client)
        self.teams = TeamsAPI(self.client)

    async def close(self) -> None:
        await self.client.close()

    async def __aenter__(self) -> ClickUp:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
