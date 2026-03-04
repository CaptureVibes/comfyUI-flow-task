from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import VideoAIProcessStatus


class VideoSourceSummary(BaseModel):
    id: uuid.UUID
    platform: str | None
    blogger_name: str | None
    video_title: str | None
    source_url: str
    thumbnail_url: str | None = None
    local_video_url: str | None = None
    video_url: str | None = None
    view_count: int | None = None

    model_config = {"from_attributes": True}


class VideoAITemplateCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    video_source_id: uuid.UUID | None = None
    prompt_description: str | None = None
    extracted_shots: list | None = None
    extra: dict | None = None


class VideoAITemplatePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    video_source_id: uuid.UUID | None = None
    prompt_description: str | None = None
    extracted_shots: list | None = None
    extra: dict | None = None


class VideoAITemplateRead(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID | None
    title: str
    description: str | None
    video_source_id: uuid.UUID | None
    video_source: VideoSourceSummary | None
    process_status: VideoAIProcessStatus
    process_error: str | None
    prompt_description: str | None
    extracted_shots: list | None
    extra: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VideoAITemplateListItem(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID | None = None
    owner_username: str | None = None
    title: str
    description: str | None
    video_source_id: uuid.UUID | None
    video_source: VideoSourceSummary | None = None
    process_status: VideoAIProcessStatus
    process_error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VideoAITemplateListResponse(BaseModel):
    items: list[VideoAITemplateListItem]
    total: int
    page: int
    page_size: int
