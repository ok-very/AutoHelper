"""Pydantic models for ClickUp API v2 responses."""

from typing import Any

from pydantic import BaseModel, Field


# ── Common ────────────────────────────────────────────────────────────────


class ClickUpUser(BaseModel):
    id: int
    username: str
    email: str | None = None
    color: str | None = ""
    profile_picture: str | None = Field(None, alias="profilePicture")
    initials: str | None = None

    model_config = {"populate_by_name": True}


class ClickUpStatus(BaseModel):
    status: str
    color: str = ""
    orderindex: int = 0
    type: str = ""


class ClickUpPriority(BaseModel):
    color: str = ""
    id: str
    orderindex: str = "0"
    priority: str


# ── Workspace / Team ─────────────────────────────────────────────────────


class ClickUpMember(BaseModel):
    user: ClickUpUser


class ClickUpTeam(BaseModel):
    id: str
    name: str
    color: str = ""
    avatar: str | None = None
    members: list[ClickUpMember] = Field(default_factory=list)


class TeamsResponse(BaseModel):
    teams: list[ClickUpTeam] = Field(default_factory=list)


# ── Spaces ────────────────────────────────────────────────────────────────


class ClickUpSpace(BaseModel):
    id: str
    name: str
    private: bool = False
    statuses: list[ClickUpStatus] = Field(default_factory=list)
    multiple_assignees: bool = False
    features: dict[str, Any] = Field(default_factory=dict)


class SpacesResponse(BaseModel):
    spaces: list[ClickUpSpace] = Field(default_factory=list)


# ── Shared Refs ───────────────────────────────────────────────────────────


class ClickUpFolderRef(BaseModel):
    id: str
    name: str
    hidden: bool = False
    access: bool = True


class ClickUpSpaceRef(BaseModel):
    id: str
    name: str = ""
    access: bool = True


# ── Lists ─────────────────────────────────────────────────────────────────


class ClickUpList(BaseModel):
    id: str
    name: str
    orderindex: int = 0
    content: str = ""
    task_count: int | None = None
    due_date: str | None = None
    start_date: str | None = None
    folder: ClickUpFolderRef = Field(
        default_factory=lambda: ClickUpFolderRef(id="", name="")
    )
    space: ClickUpSpaceRef = Field(default_factory=lambda: ClickUpSpaceRef(id=""))
    statuses: list[ClickUpStatus] = Field(default_factory=list)


class ListsResponse(BaseModel):
    lists: list[ClickUpList] = Field(default_factory=list)


# ── Folders ───────────────────────────────────────────────────────────────


class ClickUpFolder(BaseModel):
    id: str
    name: str
    orderindex: int = 0
    override_statuses: bool = False
    hidden: bool = False
    space: ClickUpSpaceRef = Field(default_factory=lambda: ClickUpSpaceRef(id=""))
    task_count: str = "0"
    lists: list[ClickUpList] = Field(default_factory=list)


class FoldersResponse(BaseModel):
    folders: list[ClickUpFolder] = Field(default_factory=list)


# ── Custom Fields ─────────────────────────────────────────────────────────


class ClickUpCustomFieldOption(BaseModel):
    id: str
    name: str
    color: str | None = None
    orderindex: int = 0


class ClickUpCustomField(BaseModel):
    id: str
    name: str
    type: str
    type_config: dict[str, Any] = Field(default_factory=dict)
    date_created: str = ""
    hide_from_guests: bool = False
    required: bool = False


class ClickUpCustomFieldValue(BaseModel):
    id: str
    name: str = ""
    type: str = ""
    type_config: dict[str, Any] = Field(default_factory=dict)
    value: Any = None


class FieldsResponse(BaseModel):
    fields: list[ClickUpCustomField] = Field(default_factory=list)


# ── Tags ──────────────────────────────────────────────────────────────────


class ClickUpTag(BaseModel):
    name: str
    tag_fg: str = ""
    tag_bg: str = ""


# ── Tasks ─────────────────────────────────────────────────────────────────


class ClickUpTask(BaseModel):
    id: str
    custom_id: str | None = None
    name: str
    text_content: str | None = None
    description: str | None = None
    status: ClickUpStatus = Field(default_factory=lambda: ClickUpStatus(status=""))
    orderindex: str = "0"
    date_created: str = ""
    date_updated: str = ""
    date_closed: str | None = None
    date_done: str | None = None
    creator: ClickUpUser | None = None
    assignees: list[ClickUpUser] = Field(default_factory=list)
    tags: list[ClickUpTag] = Field(default_factory=list)
    parent: str | None = None
    priority: ClickUpPriority | None = None
    due_date: str | None = None
    start_date: str | None = None
    points: float | None = None
    time_estimate: int | None = None
    time_spent: int | None = None
    custom_fields: list[ClickUpCustomFieldValue] = Field(default_factory=list)
    list: dict[str, Any] = Field(default_factory=dict)
    folder: dict[str, Any] = Field(default_factory=dict)
    space: dict[str, Any] = Field(default_factory=dict)
    url: str = ""


class TasksResponse(BaseModel):
    tasks: list[ClickUpTask] = Field(default_factory=list)
    last_page: bool = True


# ── Request Bodies ────────────────────────────────────────────────────────


class CreateTaskData(BaseModel):
    name: str
    description: str | None = None
    markdown_content: str | None = None
    parent: str | None = None
    assignees: list[int] | None = None
    tags: list[str] | None = None
    status: str | None = None
    priority: int | None = None
    due_date: int | None = None
    due_date_time: bool | None = None
    start_date: int | None = None
    start_date_time: bool | None = None
    time_estimate: int | None = None
    notify_all: bool | None = None
    custom_fields: list[dict[str, Any]] | None = None


class UpdateTaskData(BaseModel):
    name: str | None = None
    description: str | None = None
    markdown_content: str | None = None
    status: str | None = None
    priority: int | None = None
    due_date: int | None = None
    due_date_time: bool | None = None
    start_date: int | None = None
    start_date_time: bool | None = None
    time_estimate: int | None = None
    parent: str | None = None
