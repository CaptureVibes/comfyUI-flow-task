from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TaskStatus

# 重新导出其他模块的 schema，保持向后兼容
from app.schemas.subtask import (  # noqa: F401
    GeneratedImageBase,
    GeneratedImageRead,
    GeneratedVideoBase,
    GeneratedVideoRead,
    PhotoBase,
    PhotoRead,
    SubTaskBase,
    SubTaskCreate,
    SubTaskRead,
    SubTaskStatusPatchRequest,
    SubTaskStatusPatchResponse,
    SubTaskUpdate,
)
from app.schemas.callback import (  # noqa: F401
    CallbackGeneratedImageItem,
    CallbackGeneratedVideoItem,
    CallbackSubTaskGeneratedImagesRequest,
    CallbackSubTaskGeneratedImagesResponse,
    CallbackSubTaskGeneratedVideosRequest,
    CallbackSubTaskGeneratedVideosResponse,
    CallbackSubTaskStatusRequest,
    CallbackSubTaskStatusResponse,
)
from app.schemas.template import (  # noqa: F401
    TaskTemplateCreate,
    TaskTemplateCreateTaskRequest,
    TaskTemplateDeleteResponse,
    TaskTemplateListItem,
    TaskTemplateListResponse,
    TaskTemplatePatch,
    TaskTemplateRead,
    TemplateSubTaskBase,
)


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    extra: dict = Field(default_factory=dict)
    subtasks: list[SubTaskCreate] = Field(default_factory=list)
    workflow_json: dict | None = None
    workflow_filename: str | None = None
    schedule_enabled: bool = False
    schedule_at: datetime | None = None
    schedule_time: str | None = None
    schedule_port: int | None = None
    schedule_auto_dispatch: bool = True


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    extra: dict | None = None
    subtasks: list[SubTaskCreate] | None = None
    workflow_json: dict | None = None
    workflow_filename: str | None = None
    schedule_enabled: bool | None = None
    schedule_at: datetime | None = None
    schedule_time: str | None = None
    schedule_port: int | None = None
    schedule_auto_dispatch: bool | None = None


class TaskRead(BaseModel):
    id: UUID
    title: str
    description: str | None
    status: TaskStatus
    comfy_message: str | None
    extra: dict
    execution_state: str | None = None
    workflow_json: dict | None
    workflow_filename: str | None = None
    schedule_enabled: bool = False
    schedule_at: datetime | None = None
    schedule_time: str | None = None
    schedule_port: int | None = None
    schedule_auto_dispatch: bool = True
    schedule_last_triggered_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    subtasks: list[SubTaskRead] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class TaskListItem(BaseModel):
    id: UUID
    title: str
    description: str | None
    status: TaskStatus
    execution_state: str | None = None
    schedule_enabled: bool = False
    schedule_at: datetime | None = None
    schedule_time: str | None = None
    schedule_port: int | None = None
    schedule_auto_dispatch: bool = True
    schedule_last_triggered_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    subtask_count: int
    has_workflow: bool
    workflow_node_count: int = 0


class TaskListResponse(BaseModel):
    items: list[TaskListItem]
    total: int
    page: int
    page_size: int


class TaskDeleteResponse(BaseModel):
    id: UUID
    deleted_subtask_count: int


class TaskStatusPatchRequest(BaseModel):
    status: TaskStatus
    message: str | None = Field(default=None, max_length=2000)


class TaskStatusPatchResponse(BaseModel):
    id: UUID
    status: TaskStatus
    message: str | None = None
