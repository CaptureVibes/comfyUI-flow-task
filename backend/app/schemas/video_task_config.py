"""Schemas for video task AI scoring configuration."""
from __future__ import annotations

from pydantic import BaseModel, Field


class RoundConfig(BaseModel):
    """Configuration for a single AI scoring round."""

    enabled: bool = True
    prompt: str = ""
    model: str = "gemini-3.1-pro-preview"
    threshold: float = Field(default=60.0, ge=0, le=100)
    weight: float = Field(default=0.5, ge=0, le=1)


class VideoTaskConfigRead(BaseModel):
    """Read view of video task config (per-owner singleton)."""

    round1_enabled: bool = True
    round1_prompt: str = ""
    round1_model: str = "gemini-3.1-pro-preview"
    round1_threshold: float = 60.0
    round1_weight: float = 0.7

    round2_enabled: bool = True
    round2_prompt: str = ""
    round2_model: str = "gemini-3.1-pro-preview"
    round2_threshold: float = 70.0
    round2_weight: float = 0.3

    final_threshold: float = 65.0

    auto_publish_enabled: bool = False
    auto_publish_model: str = "gemini-3.1-pro-preview"
    auto_publish_prompt: str = ""


class VideoTaskConfigUpdate(BaseModel):
    """Update payload for video task config."""

    round1_enabled: bool | None = None
    round1_prompt: str | None = None
    round1_model: str | None = None
    round1_threshold: float | None = None
    round1_weight: float | None = None

    round2_enabled: bool | None = None
    round2_prompt: str | None = None
    round2_model: str | None = None
    round2_threshold: float | None = None
    round2_weight: float | None = None

    final_threshold: float | None = None

    auto_publish_enabled: bool | None = None
    auto_publish_model: str | None = None
    auto_publish_prompt: str | None = None
