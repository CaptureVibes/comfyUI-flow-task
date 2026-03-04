from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PhotoSourceType, TaskStatus


class PhotoBase(BaseModel):
    source_type: PhotoSourceType
    url: str
    object_key: str | None = None
    sort_order: int = 0


class PhotoRead(PhotoBase):
    id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class GeneratedImageBase(BaseModel):
    url: str
    object_key: str | None = None
    sort_order: int = 0
    extra: dict = Field(default_factory=dict)


class GeneratedImageRead(GeneratedImageBase):
    id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class GeneratedVideoBase(BaseModel):
    url: str
    object_key: str | None = None
    sort_order: int = 0
    extra: dict = Field(default_factory=dict)


class GeneratedVideoRead(GeneratedVideoBase):
    id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SubTaskBase(BaseModel):
    platform: str = Field(min_length=1, max_length=50)
    account_name: str = Field(min_length=1, max_length=100)
    account_no: str = Field(min_length=1, max_length=100)
    publish_at: datetime | None = None
    extra: dict = Field(default_factory=dict)


class SubTaskCreate(SubTaskBase):
    photos: list[PhotoBase] = Field(default_factory=list)


class SubTaskUpdate(BaseModel):
    platform: str | None = None
    account_name: str | None = None
    account_no: str | None = None
    publish_at: datetime | None = None
    extra: dict | None = None
    photos: list[PhotoBase] | None = None


class SubTaskRead(SubTaskBase):
    id: UUID
    task_id: UUID
    status: TaskStatus
    result: dict
    created_at: datetime
    updated_at: datetime
    photos: list[PhotoRead] = Field(default_factory=list)
    generated_images: list[GeneratedImageRead] = Field(default_factory=list)
    generated_videos: list[GeneratedVideoRead] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class SubTaskStatusPatchRequest(BaseModel):
    status: TaskStatus
    message: str | None = Field(default=None, max_length=2000)
    result: dict | None = None


class SubTaskStatusPatchResponse(BaseModel):
    id: UUID
    task_id: UUID
    status: TaskStatus
    result: dict
