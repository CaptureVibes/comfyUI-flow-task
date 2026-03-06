from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EvoLinkSetting(Base):
    __tablename__ = "evolink_settings"

    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    api_key: Mapped[str] = mapped_column(Text, nullable=False, default="")
    api_base_url: Mapped[str] = mapped_column(Text, nullable=False, default="https://api.evolink.ai")

    # 步骤一：视频整体理解
    understand_model: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    understand_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    understand_temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.3)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
