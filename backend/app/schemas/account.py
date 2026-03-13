from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class SocialBindingYouTube(BaseModel):
    platform: Literal["youtube"]
    channel_id: str = ""
    api_key: str = ""
    refresh_token: str = ""


class SocialBindingTikTok(BaseModel):
    platform: Literal["tiktok"]
    open_id: str = ""
    access_token: str = ""
    refresh_token: str = ""
    expires_in: int = 0


class SocialBindingInstagram(BaseModel):
    platform: Literal["instagram"]
    user_id: str = ""
    access_token: str = ""
    account_type: str = ""


SocialBinding = Annotated[
    Union[SocialBindingYouTube, SocialBindingTikTok, SocialBindingInstagram],
    Field(discriminator="platform"),
]


class AccountCreate(BaseModel):
    account_name: str = Field(min_length=1, max_length=200)
    style_description: str | None = None
    model_appearance: str | None = None
    avatar_url: str | None = None
    photo_url: str | None = None
    social_bindings: list[dict] | None = None


class AccountPatch(BaseModel):
    account_name: str | None = Field(default=None, min_length=1, max_length=200)
    style_description: str | None = None
    model_appearance: str | None = None
    avatar_url: str | None = None
    photo_url: str | None = None
    social_bindings: list[dict] | None = None


class AIGenerateBody(BaseModel):
    tag_ids: list[uuid.UUID]


class AIGenerationAnalysisItem(BaseModel):
    video_source_id: str
    video_url: str
    status: str = "pending"
    description: str = ""
    error_message: str = ""


class AIGenerationPhotoCandidate(BaseModel):
    candidate_id: str
    video_source_id: str
    video_url: str
    status: str = "pending"
    analysis_description: str = ""
    generated_photo_url: str = ""
    error_message: str = ""
    started_at: str | None = None
    finished_at: str | None = None


class SelectPhotoCandidateBody(BaseModel):
    candidate_id: str


class AIGenerateStatusResponse(BaseModel):
    account_id: str
    status: str
    error_message: str = ""
    all_video_count: int = 0
    analysis_sample_size: int = 10
    analysis_video_ids: list[str] = Field(default_factory=list)
    analysis_items: list[AIGenerationAnalysisItem] = Field(default_factory=list)
    generated_name: str = ""
    generated_avatar_url: str = ""
    generated_photo_url: str = ""
    photo_candidate_count: int = 0
    photo_candidates: list[AIGenerationPhotoCandidate] = Field(default_factory=list)
    selected_photo_candidate_id: str | None = None
    combined_description: str = ""


class BoundTagRead(BaseModel):
    id: uuid.UUID
    name: str
    color: str | None = None

    model_config = {"from_attributes": True}


class BindTagBody(BaseModel):
    tag_id: uuid.UUID


class BoundBloggerRead(BaseModel):
    id: uuid.UUID
    blogger_name: str
    blogger_handle: str | None
    avatar_url: str | None
    platform: str | None

    model_config = {"from_attributes": True}


class ScheduledPublishConfig(BaseModel):
    """AI博主定时发布配置"""
    publish_enabled: bool = False
    publish_cron: str | None = None
    publish_window_minutes: int = 0
    publish_count: int = 1


class AccountRead(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID | None
    account_name: str
    style_description: str | None
    model_appearance: str | None
    avatar_url: str | None
    photo_url: str | None = None
    social_bindings: list | None
    tiktok_bloggers: list[BoundBloggerRead] = []
    bound_tags: list[BoundTagRead] = []
    publish_enabled: bool = False
    publish_cron: str | None = None
    publish_window_minutes: int = 0
    publish_count: int = 1
    ai_generation_status: str = "idle"
    ai_generation_error: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AccountListResponse(BaseModel):
    items: list[AccountRead]
    total: int
    page: int
    page_size: int
