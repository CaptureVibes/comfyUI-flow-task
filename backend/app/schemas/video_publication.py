import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VideoPublicationCreate(BaseModel):
    """创建发布任务请求"""
    sub_task_id: uuid.UUID
    video_url: str
    title: str
    description: str | None = None
    tags: list[str] | None = None
    channels: list[dict]  # [{platform, channel_id, title?, description?, tags?, privacy_level?}]
    callback_url: str | None = None


class VideoPublicationChannelStatus(BaseModel):
    """单个渠道的发布状态"""
    platform: str
    channel_id: str
    channel_name: str | None = None
    status: str  # pending, uploading, completed, failed
    platform_video_id: str | None = None
    platform_video_url: str | None = None
    upload_id: int | str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    uploaded_at: datetime | None = None


class VideoPublicationRead(BaseModel):
    """发布任务读取"""
    id: uuid.UUID
    sub_task_id: uuid.UUID
    open_api_task_id: str | None = None
    external_id: str | None = None
    status: str
    total_channels: int
    completed_channels: int
    failed_channels: int
    channels_status: list[VideoPublicationChannelStatus] | None = None
    error_message: str | None = None
    callback_received: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class VideoPublicationDetailRead(VideoPublicationRead):
    """发布任务详情（包含请求数据）"""
    request_payload: dict | None = None
    response_data: dict | None = None


class VideoPublicationStatusUpdate(BaseModel):
    """更新发布任务状态（用于回调）"""
    task_id: str  # Open API task_id
    external_id: str | None = None
    status: str
    total_channels: int | None = None
    completed_channels: int | None = None
    failed_channels: int | None = None
    channels: list[dict] | None = None
    completed_at: datetime | None = None
    timestamp: int
    signature: str
