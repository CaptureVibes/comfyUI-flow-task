import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


class DailyGenerationCreate(BaseModel):
    owner_id: uuid.UUID
    target_date: date
    prompt: str
    image: str
    duration: str
    shots: list | None = None


class DailyGenerationRead(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    account_id: uuid.UUID | None = None
    template_id: uuid.UUID | None = None
    target_date: date
    sort_order: int
    status: str
    prompt: str
    image: str
    duration: str
    shots: list | None = None
    # [{"video_url": "...", "thumbnail_url": "..."}, ...]
    result_videos: list[dict[str, Any]] | None = None
    selected_video_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DailyGenerationStatusUpdate(BaseModel):
    status: str
    # For setting result videos (generating → reviewing)
    result_videos: list[dict[str, Any]] | None = None
    # Required when transitioning reviewing → pending_publish
    selected_video_url: str | None = None

    @model_validator(mode="after")
    def validate_selection(self) -> "DailyGenerationStatusUpdate":
        if self.status == "pending_publish" and not self.selected_video_url:
            raise ValueError("进入待发布阶段时必须提供 selected_video_url")
        return self
