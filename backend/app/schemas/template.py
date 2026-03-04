from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TemplateSubTaskBase(BaseModel):
    platform: str = Field(min_length=1, max_length=50)
    account_name: str = Field(min_length=1, max_length=100)
    account_no: str = Field(min_length=1, max_length=100)
    publish_at: datetime | None = None
    extra: dict = Field(default_factory=dict)


class TaskTemplateCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    extra: dict = Field(default_factory=dict)
    subtasks: list[TemplateSubTaskBase] = Field(default_factory=list)
    workflow_json: dict | None = None


class TaskTemplatePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    extra: dict | None = None
    subtasks: list[TemplateSubTaskBase] | None = None
    workflow_json: dict | None = None


class TaskTemplateRead(BaseModel):
    id: UUID
    title: str
    description: str | None
    extra: dict
    subtasks: list[TemplateSubTaskBase]
    workflow_json: dict | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TaskTemplateListItem(BaseModel):
    id: UUID
    title: str
    description: str | None
    subtask_count: int
    created_at: datetime
    updated_at: datetime


class TaskTemplateListResponse(BaseModel):
    items: list[TaskTemplateListItem]
    total: int
    page: int
    page_size: int


class TaskTemplateDeleteResponse(BaseModel):
    id: UUID


class TaskTemplateCreateTaskRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    extra: dict | None = None
