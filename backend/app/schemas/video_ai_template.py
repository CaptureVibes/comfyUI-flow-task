from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import VideoAIProcessStatus


class TagRead(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID | None
    name: str
    color: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class VideoSourceSummary(BaseModel):
    id: uuid.UUID
    platform: str | None
    blogger_name: str | None
    video_title: str | None
    source_url: str
    thumbnail_url: str | None = None
    local_video_url: str | None = None
    local_gcs_video_url: str | None = None
    video_url: str | None = None
    view_count: int | None = None
    duration: int | None = None

    model_config = {"from_attributes": True}


class VideoAITemplateCreate(BaseModel):
    title: str = Field(min_length=1)
    description: str | None = None
    video_source_id: uuid.UUID | None = None
    prompt_description: str | None = None
    extracted_shots: list | None = None
    extra: dict | None = None
    tag_ids: list[uuid.UUID] | None = None


class VideoAITemplatePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1)
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
    is_used: bool = False
    repeatable: bool = False
    tiktok_blogger_id: uuid.UUID | None = None
    tags: list[TagRead] = []
    extra: dict | None
    lookbooks: list | None = None
    remix_history: list | None = None
    remix_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── 阶段 2.5 (lookbook) 相关 schemas ──────────────────────────────────────

class LookbookPanelRead(BaseModel):
    index: int                          # 1..8
    image_url: str
    is_reference: bool = False
    used_in_remix_id: uuid.UUID | None = None


class LookbookRead(BaseModel):
    outfit_index: int
    outfit_shot_image_url: str
    generated_prompt: str | None = None
    lookbook_image_url: str | None = None
    panels: list[LookbookPanelRead] = []
    regenerated_count: int = 0
    last_regenerated_at: datetime | None = None


class RemixHistoryItem(BaseModel):
    remix_id: uuid.UUID
    outfit_index: int
    panel_index: int
    panel_image_url: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    status: str                          # running / success / failed
    error_message: str | None = None
    downstream_result: dict | None = None


class RemixRequest(BaseModel):
    """POST /{tpl_id}/remix body —— 全可选，缺省时自动挑下一个未用 panel。"""
    outfit_index: int | None = None
    panel_index: int | None = None


class RemixResponse(BaseModel):
    remix_id: uuid.UUID
    outfit_index: int
    panel_index: int
    panel_image_url: str
    status: str


class LookbooksStateRead(BaseModel):
    """GET /{tpl_id}/lookbooks 返回结构。"""
    lookbooks: list[LookbookRead] = []
    remix_history: list[RemixHistoryItem] = []
    remix_count: int = 0
    process_status: VideoAIProcessStatus


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
    prompt_description: str | None = None
    extracted_shots: list | None = None
    is_used: bool = False
    repeatable: bool = False
    tiktok_blogger_id: uuid.UUID | None = None
    tags: list[TagRead] = []
    generated_video_count: int = 0
    last_published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VideoAITemplateListResponse(BaseModel):
    items: list[VideoAITemplateListItem]
    total: int
    page: int
    page_size: int
