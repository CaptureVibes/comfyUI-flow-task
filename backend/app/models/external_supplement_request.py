from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, JSON, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ExternalSupplementRequest(Base):
    """跟踪「补充模板」外包给 vendor 的请求生命周期。

    一次 outbound 一行；vendor 的回调通过 request_id 反查到这一行，
    用 callback_secret 验签后再处理 videos。
    """

    __tablename__ = "external_supplement_requests"
    __table_args__ = (
        UniqueConstraint("request_id", name="uq_external_supplement_requests_request_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)            # "exclusive" | "auto"
    target_video_count: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    filters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    account_ids: Mapped[list] = mapped_column(JSON, nullable=False)          # list[uuid str]
    callback_secret: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    # pending | partial | completed | failed

    vendor_request_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    vendor_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    callbacks_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    videos_accepted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    videos_duplicated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    videos_rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # AI 审核 / 分类未通过的视频明细，便于这次请求事后查看；元素结构见 _append_rejected_video
    rejected_videos: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
