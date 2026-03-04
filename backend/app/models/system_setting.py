from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(32), primary_key=True, default="default")

    # ComfyUI
    comfyui_server_ip: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    comfyui_ports: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # EvoLink
    evolink_api_key: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evolink_api_base_url: Mapped[str] = mapped_column(Text, nullable=False, default="https://api.evolink.ai")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
