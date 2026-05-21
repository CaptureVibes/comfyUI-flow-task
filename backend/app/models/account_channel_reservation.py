from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AccountChannelReservation(Base):
    """占用 AI 博主的某个平台频道名额，避免外部流程重复领取。"""

    __tablename__ = "account_channel_reservations"
    __table_args__ = (
        UniqueConstraint("account_id", "platform", name="uq_account_channel_reservations_account_platform"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="reserved", index=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="openapi")
    channel_source: Mapped[str] = mapped_column(String(50), nullable=False, default="openapi", index=True)
    channel_id: Mapped[str | None] = mapped_column(String(300), nullable=True, index=True)
    channel_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    username: Mapped[str | None] = mapped_column(String(300), nullable=True, index=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    channel_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    channel_status: Mapped[str] = mapped_column(String(30), nullable=False, default="active", index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # KOL 长/短链（来自 kol_service.build_long_link + encode_short_link，按本 reservation 的 platform 生成）
    kol_long_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    kol_short_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    reserved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
