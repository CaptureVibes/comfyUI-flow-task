from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class VideoTaskConfig(Base):
    """Per-owner configuration for video task pipeline and publish pool thresholds."""

    __tablename__ = "video_task_configs"

    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)

    # ── Publish Pool Thresholds ────────────────────────────────────────────────
    # Videos with has_ng=True → always abandoned (never enter pool)
    # weighted_total_score >= score_threshold_high → queued (enter pool)
    # weighted_total_score < score_threshold_low → abandoned (discarded)
    # score_threshold_low <= weighted_total_score < score_threshold_high → random(pool_ratio) → queued or abandoned
    score_threshold_high: Mapped[float] = mapped_column(Float, nullable=False, default=60.0)
    score_threshold_low: Mapped[float] = mapped_column(Float, nullable=False, default=20.0)
    pool_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.75)

    # ── Auto Publish Metadata Generation ──────────────────────────────────────
    # AI generates title/desc/hashtag before auto-publishing queued videos
    auto_publish_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    auto_publish_model: Mapped[str] = mapped_column(String(200), nullable=False, default="gemini-3.1-pro-preview")
    auto_publish_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
