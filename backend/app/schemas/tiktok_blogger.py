from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TiktokBloggerCreate(BaseModel):
    platform: str = Field(min_length=1, max_length=50)
    blogger_id: str = Field(min_length=1, max_length=200)
    blogger_name: str = Field(min_length=1, max_length=200)
    blogger_handle: str | None = None
    blogger_url: str | None = None
    avatar_url: str | None = None


class TiktokBloggerFromUrl(BaseModel):
    """Create blogger by parsing a profile URL."""
    profile_url: str = Field(min_length=1)


class TiktokBloggerPatch(BaseModel):
    blogger_name: str | None = None
    blogger_handle: str | None = None
    blogger_url: str | None = None
    avatar_url: str | None = None


class TiktokBloggerRead(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID | None
    platform: str
    blogger_id: str
    blogger_name: str
    blogger_handle: str | None
    blogger_url: str | None
    avatar_url: str | None
    video_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TiktokBloggerListResponse(BaseModel):
    items: list[TiktokBloggerRead]
    total: int
    page: int
    page_size: int
