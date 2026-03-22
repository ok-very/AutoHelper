"""Monday.com board data types for the import pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MondayGroup:
    id: str
    title: str
    stage: int | None = None  # parsed from title "Stage N: ..."


@dataclass
class MondayColumn:
    id: str
    title: str
    type: str
    settings: dict = field(default_factory=dict)


@dataclass
class MondayUpdate:
    id: str
    body_html: str
    body_text: str
    created_at: str
    creator_name: str


@dataclass
class MondaySubitem:
    id: str
    name: str
    status: str = ""
    people: str | None = None
    target_date: str | None = None
    notes: str | None = None
    email_template: str | None = None
    files: list[str] = field(default_factory=list)


@dataclass
class MondayItem:
    id: str
    name: str
    group_id: str
    group_title: str
    status: str = ""
    pm_name: str | None = None
    target_date: str | None = None
    notes: str | None = None
    label: str | None = None
    timeline: str | None = None
    subitems: list[MondaySubitem] = field(default_factory=list)
    updates: list[MondayUpdate] = field(default_factory=list)
    files: list[str] = field(default_factory=list)


@dataclass
class MondayBoardData:
    id: str
    name: str
    developer: str
    project: str
    groups: list[MondayGroup] = field(default_factory=list)
    columns: list[MondayColumn] = field(default_factory=list)
    items: list[MondayItem] = field(default_factory=list)


@dataclass
class StagedCorrespondence:
    """A piece of correspondence matched to a BFA template task."""

    temp_id: str
    template_key: str | None = None
    content: str = ""
    content_html: str | None = None
    source: str = "update"  # "update" or "email_template"
    created_at: str | None = None
    creator: str | None = None
