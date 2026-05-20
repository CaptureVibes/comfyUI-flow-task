"""Schema for /api/v1/external/supplement-callback。"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ── outbound 出参/入参（请求 vendor）────────────────────────────────────────────

class SupplementFilters(BaseModel):
    """三个过滤条件，None / 0 视为不限。"""
    min_view_count: int | None = None
    published_after: date | None = None
    max_duration_seconds: int | None = None


# ── 回调请求体（vendor → 我们）─────────────────────────────────────────────────

class CallbackVideo(BaseModel):
    """callback 里 items[].videos[] 单条。

    必填: source_url, local_video_url
    其余字段缺失则置 NULL，不影响入库。
    """
    source_url: str
    local_video_url: str       # `gs://bucket/...mp4` 或 https://...mp4

    blogger_name: str | None = None
    video_title: str | None = None
    video_desc: str | None = None
    publish_date: datetime | None = None
    duration: int | None = None       # 秒
    view_count: int | None = None
    like_count: int | None = None
    favorite_count: int | None = None
    comment_count: int | None = None
    share_count: int | None = None
    thumbnail_url: str | None = None
    width: int | None = None
    height: int | None = None
    aspect_ratio: float | None = None
    extra: dict | None = None


class CallbackItem(BaseModel):
    account_id: uuid.UUID
    status: Literal["completed", "partial", "failed", "skipped"]
    error: str | None = None
    videos: list[CallbackVideo] = Field(default_factory=list)


class SupplementCallbackBody(BaseModel):
    request_id: uuid.UUID
    mode: Literal["exclusive", "auto"]
    final: bool
    items: list[CallbackItem] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")


class SupplementCallbackResponse(BaseModel):
    request_id: uuid.UUID
    accepted: int = 0
    duplicated: int = 0
    rejected: int = 0
    message: str = "ok"
