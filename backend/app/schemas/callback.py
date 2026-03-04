from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import TaskStatus
from app.schemas.subtask import GeneratedImageRead, GeneratedVideoRead


class CallbackSubTaskStatusRequest(BaseModel):
    subtask_id: UUID
    status: TaskStatus
    message: str | None = Field(default=None, max_length=2000)
    result: dict | None = None


class CallbackSubTaskStatusResponse(BaseModel):
    subtask_id: UUID
    subtask_status: TaskStatus
    task_id: UUID
    task_status: TaskStatus
    result: dict


class CallbackGeneratedImageItem(BaseModel):
    url: str = Field(min_length=1)
    object_key: str | None = None
    sort_order: int = Field(default=0, ge=0)
    extra: dict = Field(default_factory=dict)


class CallbackSubTaskGeneratedImagesRequest(BaseModel):
    subtask_id: UUID
    images: list[CallbackGeneratedImageItem] = Field(default_factory=list)


class CallbackSubTaskGeneratedImagesResponse(BaseModel):
    subtask_id: UUID
    task_id: UUID
    saved_count: int
    images: list[GeneratedImageRead] = Field(default_factory=list)


class CallbackGeneratedVideoItem(BaseModel):
    url: str = Field(min_length=1)
    object_key: str | None = None
    sort_order: int = Field(default=0, ge=0)
    extra: dict = Field(default_factory=dict)


class CallbackSubTaskGeneratedVideosRequest(BaseModel):
    subtask_id: UUID
    videos: list[CallbackGeneratedVideoItem] = Field(default_factory=list)


class CallbackSubTaskGeneratedVideosResponse(BaseModel):
    subtask_id: UUID
    task_id: UUID
    saved_count: int
    videos: list[GeneratedVideoRead] = Field(default_factory=list)
