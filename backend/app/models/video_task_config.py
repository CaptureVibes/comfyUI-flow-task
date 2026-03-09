from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class VideoTaskConfig(Base):
    """Per-owner configuration for two-round AI scoring of generated videos."""

    __tablename__ = "video_task_configs"

    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)

    # ── Round 1 ──────────────────────────────────────────────────────────────
    round1_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    round1_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    round1_model: Mapped[str] = mapped_column(String(200), nullable=False, default="gemini-2.0-flash")
    round1_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=60.0)
    round1_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)

    # ── Round 2 ──────────────────────────────────────────────────────────────
    round2_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    round2_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    round2_model: Mapped[str] = mapped_column(String(200), nullable=False, default="gemini-2.0-flash")
    round2_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=70.0)
    round2_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.3)

    # ── Final Threshold ────────────────────────────────────────────────────────
    # Weighted average score must be >= this threshold to enter "pending_publish" state
    final_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=65.0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
