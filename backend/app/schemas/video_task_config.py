"""Schemas for video task pipeline and publish pool configuration."""
from __future__ import annotations

from pydantic import BaseModel, Field


class VideoTaskConfigRead(BaseModel):
    """Read view of video task config (per-owner singleton)."""

    score_threshold_high: float = 60.0   # AI感进入候选池分数线
    score_threshold_low: float = 20.0    # AI感丢弃分数线
    pool_ratio: float = 0.75             # 中间区间进入候选池比例

    auto_publish_enabled: bool = False
    auto_publish_model: str = "gemini-3.1-pro-preview"
    auto_publish_prompt: str = ""


class VideoTaskConfigUpdate(BaseModel):
    """Update payload for video task config."""

    score_threshold_high: float | None = Field(default=None, ge=0, le=100)
    score_threshold_low: float | None = Field(default=None, ge=0, le=100)
    pool_ratio: float | None = Field(default=None, ge=0, le=1)

    auto_publish_enabled: bool | None = None
    auto_publish_model: str | None = None
    auto_publish_prompt: str | None = None
