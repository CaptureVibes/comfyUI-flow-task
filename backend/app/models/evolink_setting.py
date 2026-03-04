from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EvoLinkSetting(Base):
    __tablename__ = "evolink_settings"

    key: Mapped[str] = mapped_column(String(32), primary_key=True, default="default")
    api_key: Mapped[str] = mapped_column(Text, nullable=False, default="")
    api_base_url: Mapped[str] = mapped_column(Text, nullable=False, default="https://api.evolink.ai")

    # 步骤一：视频整体理解
    understand_model: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    understand_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    understand_temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.3)
    understand_output_format: Mapped[str] = mapped_column(String(20), nullable=False, default="text")
    understand_json_schema: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # 步骤二：造型描述提取
    extract_model: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    extract_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    extract_temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.3)
    extract_output_format: Mapped[str] = mapped_column(String(20), nullable=False, default="json")
    extract_json_schema: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # 步骤三：生图（Job 轮询模式）
    image_gen_model: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    image_gen_size: Mapped[str] = mapped_column(String(20), nullable=False, default="1:1")
    image_gen_quality: Mapped[str] = mapped_column(String(10), nullable=False, default="2K")
    image_gen_prompt_template: Mapped[str] = mapped_column(Text, nullable=False, default="")
    image_gen_temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    image_gen_output_format: Mapped[str] = mapped_column(String(20), nullable=False, default="text")
    image_gen_json_schema: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # 兼容旧字段（保留在DB中，不再暴露给前端）
    model_name: Mapped[str] = mapped_column(String(200), nullable=False, default="gemini-2.0-flash")
    image_gen_api_base_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    image_gen_api_key: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
