from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TiktokBlogger(Base):
    __tablename__ = "tiktok_bloggers"
    __table_args__ = (
        UniqueConstraint("owner_id", "platform", "blogger_id", name="uq_tiktok_bloggers_owner_platform_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    blogger_id: Mapped[str] = mapped_column(String(200), nullable=False)
    blogger_name: Mapped[str] = mapped_column(String(200), nullable=False)
    blogger_handle: Mapped[str | None] = mapped_column(String(200), nullable=True)
    blogger_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    video_sources: Mapped[list["VideoSource"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "VideoSource",
        back_populates="tiktok_blogger",
        lazy="select",
    )
