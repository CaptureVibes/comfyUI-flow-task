from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CandidateVideoStatus(str, enum.Enum):
    pending = "pending"
    ai_reviewing = "ai_reviewing"
    ai_passed = "ai_passed"
    ai_failed = "ai_failed"
    importing = "importing"
    imported = "imported"
    import_failed = "import_failed"


class CandidateVideo(Base):
    __tablename__ = "candidate_videos"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)

    # 关联关键词
    keyword_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    keyword_text: Mapped[str] = mapped_column(String(500), nullable=False)

    # 分类：shared | exclusive
    template_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # 博主信息
    blogger_unique_id: Mapped[str] = mapped_column(String(200), nullable=False)
    blogger_nickname: Mapped[str | None] = mapped_column(String(200), nullable=True)
    blogger_follower_count: Mapped[int | None] = mapped_column(BigInteger(), nullable=True)

    # 视频信息
    video_id: Mapped[str] = mapped_column(String(100), nullable=False)
    video_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration: Mapped[int | None] = mapped_column(nullable=True)  # 秒
    cover_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    cdn_cover_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    play_count: Mapped[int | None] = mapped_column(BigInteger(), nullable=True)
    like_count: Mapped[int | None] = mapped_column(BigInteger(), nullable=True)

    # 导入视频库重试计数（>=3 表示放弃）
    import_attempts: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)

    # 关联视频库
    video_source_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("video_sources.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    # AI 审核状态
    status: Mapped[CandidateVideoStatus] = mapped_column(
        Enum(CandidateVideoStatus, name="candidatevideostatus"),
        nullable=False,
        default=CandidateVideoStatus.pending,
        server_default="pending",
    )
    ai_reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    ai_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 手动隐藏标记：True 时前后端查询均过滤掉，不影响 status 状态机，可随时恢复
    hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        # (keyword_id, blogger_unique_id, video_id) 联合唯一：同一关键词+博主+视频不重复
        Index("uq_candidate_keyword_blogger_video", "keyword_id", "blogger_unique_id", "video_id", unique=True),
        Index("ix_candidate_videos_keyword_type", "keyword_id", "template_type"),
    )
