from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import VideoAIProcessStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class VideoAITemplate(Base):
    __tablename__ = "video_ai_templates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
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
    # 阶段 2.5 lookbook 状态：每个 outfit_shot 一个 lookbook，含 panels 池
    # 详见 app.services.video_ai_service._run_lookbook_stage 和 schemas.video_ai_template.LookbookRead
    lookbooks: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # 重洗历史：每次 remix 一行，记录 outfit_index / panel_index / status / downstream_result
    remix_history: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # 重洗次数，方便 SQL 排序 / 列表统计
    remix_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
