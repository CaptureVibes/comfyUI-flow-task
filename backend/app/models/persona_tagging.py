from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class VideoTaggingResult(Base):
    """单视频人设打标任务及结果。"""

    __tablename__ = "video_tagging_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, unique=True, index=True)
    gcs_url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # 任务状态
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    result_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # AI 分析结果
    video_description_unit: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    personal_tags: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    style_vector: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    style_signature: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    raw_outputs: Mapped[Any | None] = mapped_column(JSONB, nullable=True)

    # 任务溯源
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="direct")
    source_blogger_task_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    source_tiktok_blogger_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    # 队列锁定
    worker_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    lock_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BloggerTaggingResult(Base):
    """博主账号级人设打标任务及结果。"""

    __tablename__ = "blogger_tagging_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tiktok_blogger_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, unique=True, index=True)

    # 任务状态
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    result_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 视频计数
    min_video_count: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    available_video_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    usable_video_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_video_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_video_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    submitted_video_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # 关联视频
    selected_video_ids: Mapped[list[str] | None] = mapped_column(ARRAY(Uuid(as_uuid=True)), nullable=True)
    video_task_ids: Mapped[list[str] | None] = mapped_column(ARRAY(Uuid(as_uuid=True)), nullable=True)

    # AI 聚合结果
    account_personal_tags: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    account_style_vector: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    account_style_signature: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    account_one_sentence_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    aggregated_social_identity: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    aggregated_occasion: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    raw_outputs: Mapped[Any | None] = mapped_column(JSONB, nullable=True)

    # 队列锁定
    worker_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    lock_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
