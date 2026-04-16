from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

ChannelPlatform = Literal["youtube", "tiktok", "instagram"]


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
    account_type: Literal["persona", "shared", "exclusive"] = "exclusive"
    face_mode: Literal["face", "no_face"] = "face"
    gender: Literal["male", "female", "unisex"] = "female"
    style_description: str | None = None
    model_appearance: str | None = None
    avatar_url: str | None = None
    photo_url: str | None = None
    social_bindings: list[dict] | None = None
    hashtags: list[str] | None = None


class AccountPatch(BaseModel):
    account_name: str | None = Field(default=None, min_length=1, max_length=200)
    account_handle: str | None = None
    account_signature: str | None = None
    account_type: Literal["persona", "shared", "exclusive"] | None = None
    face_mode: Literal["face", "no_face"] | None = None
    gender: Literal["male", "female", "unisex"] | None = None  # None 表示不修改
    style_description: str | None = None
    model_appearance: str | None = None
    avatar_url: str | None = None
    photo_url: str | None = None
    social_bindings: list[dict] | None = None
    hashtags: list[str] | None = None


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
    video_source_id: str = ""
    video_url: str = ""
    source_group_index: int = 1
    candidate_number: int = 1
    status: str = "pending"
    analysis_description: str = ""
    generated_photo_url: str = ""
    error_message: str = ""
    started_at: str | None = None
    finished_at: str | None = None


class SelectPhotoCandidateBody(BaseModel):
    candidate_id: str


AIResumeStage = Literal["current", "video_analyzing", "name_generating", "photo_generating", "painting_generating", "avatar_generating"]


class ResumeAIGenerationBody(BaseModel):
    from_stage: AIResumeStage = "current"
    account_ids: list[uuid.UUID] | None = None


class BulkResumeAIAccountsResponse(BaseModel):
    status: str
    resumed_count: int = 0
    skipped_count: int = 0
    from_stage: AIResumeStage = "current"


class BulkGenerateAIAccountsResponse(BaseModel):
    status: str
    created_count: int = 0
    skipped_count: int = 0
    queued_count: int = 0
    created_account_ids: list[str] = Field(default_factory=list)
    skipped_tag_ids: list[str] = Field(default_factory=list)


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
    generated_painting_url: str = ""
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


class BoundFlagRead(BaseModel):
    id: uuid.UUID
    name: str
    color: str | None = None

    model_config = {"from_attributes": True}


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


class AccountPerformanceSnapshot(BaseModel):
    synced_at: datetime | None = None
    followers_count: int | float | None = None
    video_count: int | None = None
    total_views: int | float | None = None
    avg_views: int | float | None = None
    total_likes: int | float | None = None
    avg_like_rate: int | float | None = None
    first_content_date: datetime | None = None
    latest_video_published_at: datetime | None = None


class BulkGenerateNameHandleBody(BaseModel):
    account_ids: list[uuid.UUID] | None = None


class BulkGenerateNameHandleResponse(BaseModel):
    status: str
    queued_count: int = 0


class AccountChannelReservationRead(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    platform: str
    status: str
    source: str = "openapi"
    channel_source: str = "openapi"
    channel_id: str | None = None
    channel_name: str | None = None
    username: str | None = None
    avatar_url: str | None = None
    channel_info: dict | None = None
    channel_status: str = "active"
    note: str | None = None
    reserved_at: datetime
    confirmed_at: datetime | None = None
    bound_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReserveAIAccountsBody(BaseModel):
    gender: Literal["male", "female", "unisex"]
    platform: Literal["youtube", "tiktok"]
    count: int = Field(ge=1, le=100)
    source: str = "openapi"


class ReserveAIAccountsResponse(BaseModel):
    items: list["AccountRead"]
    requested_count: int
    reserved_count: int
    reservation_ids: list[uuid.UUID] = Field(default_factory=list)


class ConfirmChannelReservationsBody(BaseModel):
    reservation_ids: list[uuid.UUID] | None = None
    account_ids: list[uuid.UUID] | None = None
    platform: Literal["youtube", "tiktok"] | None = None


class ConfirmChannelReservationsResponse(BaseModel):
    status: str
    confirmed_count: int = 0
    reservation_ids: list[uuid.UUID] = Field(default_factory=list)


class BindOpenAPIChannelBody(BaseModel):
    platform: Literal["youtube", "tiktok"]
    channel_id: str = ""
    channel_name: str = ""
    username: str = ""
    open_id: str = ""
    access_token: str = ""
    refresh_token: str = ""
    expires_in: int = 0
    api_key: str = ""
    source: str = "openapi"
    extra: dict | None = None


class ExternalReserveAIAccountsBody(BaseModel):
    api_key: str = ""
    owner_id: uuid.UUID | None = None
    gender: Literal["male", "female", "unisex"]
    platform: ChannelPlatform
    count: int = Field(ge=1, le=100)
    source: str = "openapi"


class ExternalAIAccountCandidateItem(BaseModel):
    account_id: uuid.UUID
    platform: ChannelPlatform
    account_name: str
    account_handle: str | None = None
    account_signature: str | None = None
    hashtags: list[str] | None = None
    avatar_url: str | None = None


class ExternalReserveAIAccountsResponse(BaseModel):
    items: list[ExternalAIAccountCandidateItem]
    requested_count: int
    returned_count: int


class ExternalConfirmChannelReservationBody(BaseModel):
    api_key: str = ""
    owner_id: uuid.UUID | None = None
    account_id: uuid.UUID
    platform: ChannelPlatform


class ExternalConfirmChannelReservationResponse(BaseModel):
    status: str
    owner_id: uuid.UUID
    account_id: uuid.UUID
    platform: ChannelPlatform


class ExternalBindOpenAPIChannelBody(BaseModel):
    api_key: str = ""
    owner_id: uuid.UUID | None = None
    platform: ChannelPlatform
    channel_source: str = "openapi"
    channel_id: str = ""
    channel_name: str = ""
    username: str = ""


class ExternalReleaseChannelReservationBody(BaseModel):
    api_key: str = ""
    owner_id: uuid.UUID | None = None
    account_id: uuid.UUID
    platform: ChannelPlatform


class ExternalChannelReservationRead(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    platform: ChannelPlatform
    status: str
    source: str = "openapi"
    channel_source: str = "openapi"
    channel_id: str | None = None
    channel_name: str | None = None
    username: str | None = None
    avatar_url: str | None = None
    reserved_at: datetime
    confirmed_at: datetime | None = None
    bound_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExternalBindOpenAPIChannelResponse(BaseModel):
    account_id: uuid.UUID
    account_name: str
    account_handle: str | None = None
    account_signature: str | None = None
    gender: str
    account_type: str
    channel_reservations: list[ExternalChannelReservationRead]


class AccountRead(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID | None
    account_name: str
    account_handle: str | None = None
    account_signature: str | None = None
    account_type: str = "exclusive"
    face_mode: str = "face"
    gender: str = "female"
    style_description: str | None
    model_appearance: str | None
    avatar_url: str | None
    photo_url: str | None = None
    painting_url: str | None = None
    social_bindings: list | None = None
    channel_reservations: list[AccountChannelReservationRead] = []
    performance_snapshot: AccountPerformanceSnapshot | None = None
    hashtags: list[str] | None = None
    tiktok_bloggers: list[BoundBloggerRead] = []
    bound_tags: list[BoundTagRead] = []
    bound_flags: list[BoundFlagRead] = []
    publish_enabled: bool = False
    publish_cron: str | None = None
    publish_window_minutes: int = 0
    publish_count: int = 1
    ai_generation_status: str = "idle"
    ai_generation_error: str | None = None
    pending_publish_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AccountListResponse(BaseModel):
    items: list[AccountRead]
    total: int
    page: int
    page_size: int
