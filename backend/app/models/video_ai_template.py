from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import VideoAIProcessStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class VideoAITemplate(Base):
    __tablename__ = "video_ai_templates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    process_status: Mapped[VideoAIProcessStatus] = mapped_column(
        SAEnum(VideoAIProcessStatus, name="video_ai_process_status", create_type=False),
        nullable=False,
        default=VideoAIProcessStatus.pending,
    )
    process_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_shots: Mapped[list | None] = mapped_column(JSON, nullable=True)
    process_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    repeatable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tiktok_blogger_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tiktok_bloggers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
