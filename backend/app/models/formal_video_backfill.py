from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FormalVideoBackfill(Base):
    """临时表：账号「转正」回填映射。

    每个账号至多一条；promotion_date 标识它在哪一天被算作正式号。
    一旦写入，该账号 promotion_date 起的所有 openapi video_publication 都视为正式视频。
    """

    __tablename__ = "formal_video_backfills"
    __table_args__ = (
        UniqueConstraint("account_id", name="uq_formal_video_backfills_account_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    promotion_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    trigger_publication_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("video_publications.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
