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

    # ── Publish Pool: 3-step selection ─────────────────────────────────────────
    # Step 1: Pick top N% by score → queued
    # Step 2: Among the rest, discard those with score < discard_below
    # Step 3: Among the remaining, pick top Y% → queued
    top_percent: Mapped[float] = mapped_column(Float, nullable=False, default=30.0)
    discard_below: Mapped[float] = mapped_column(Float, nullable=False, default=40.0)
    select_percent: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)

    # ── Auto Publish Metadata Generation ──────────────────────────────────────
    # AI generates title/desc/hashtag before auto-publishing queued videos
    auto_publish_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    auto_publish_model: Mapped[str] = mapped_column(String(200), nullable=False, default="gemini-3.1-pro-preview")
    auto_publish_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
