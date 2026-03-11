from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    account_name: Mapped[str] = mapped_column(String(200), nullable=False)
    style_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_appearance: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    social_bindings: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Scheduled publish config
    publish_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    publish_cron: Mapped[str | None] = mapped_column(String(100), nullable=True)
    publish_window_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    publish_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    publish_last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
