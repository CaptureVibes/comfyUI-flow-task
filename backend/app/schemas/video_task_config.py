"""Schemas for video task pipeline and publish pool configuration."""
from __future__ import annotations

from pydantic import BaseModel, Field


class VideoTaskConfigRead(BaseModel):
    """Read view of video task config (per-owner singleton)."""

    top_percent: float = 30.0       # Step 1: 直接挑选前 N%
    discard_below: float = 40.0     # Step 2: 丢弃分数低于此值的
    select_percent: float = 50.0    # Step 3: 剩下的再选前 Y%

    auto_publish_enabled: bool = False
    auto_publish_model: str = "gemini-3.1-pro-preview"
    auto_publish_prompt: str = ""


class VideoTaskConfigUpdate(BaseModel):
    """Update payload for video task config."""

    top_percent: float | None = Field(default=None, ge=0, le=100)
    discard_below: float | None = Field(default=None, ge=0, le=100)
    select_percent: float | None = Field(default=None, ge=0, le=100)

    auto_publish_enabled: bool | None = None
    auto_publish_model: str | None = None
    auto_publish_prompt: str | None = None
