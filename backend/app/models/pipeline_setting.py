from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PipelineSetting(Base):
    __tablename__ = "pipeline_settings"

    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)

    # 第一阶段：视频理解
    understand_model: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    understand_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    understand_temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.3)
    understand_output_format: Mapped[str] = mapped_column(String(20), nullable=False, default="text")
    understand_json_schema: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # 第二阶段：抽帧生图（Nano2）
    imagegen_model: Mapped[str] = mapped_column(String(200), nullable=False, default="gemini-3.1-flash-image-preview")
    imagegen_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    imagegen_size: Mapped[str] = mapped_column(String(20), nullable=False, default="9:16")
    imagegen_quality: Mapped[str] = mapped_column(String(10), nullable=False, default="2K")

    # 第三阶段：拆分图片（Segment API）
    splitting_api_url: Mapped[str] = mapped_column(String(500), nullable=False, default="http://34.21.127.95:8080")

    # 第四阶段：去脸（Face Removing API）
    face_removing_api_url: Mapped[str] = mapped_column(String(500), nullable=False, default="http://34.86.216.234:8001")
    face_removing_score_thresh: Mapped[float] = mapped_column(Float, nullable=False, default=0.3)
    face_removing_margin_scale: Mapped[float] = mapped_column(Float, nullable=False, default=0.2)
    face_removing_head_top_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)

    # 第五阶段：图片超分（Pillow LANCZOS）
    upscaling_scale: Mapped[int] = mapped_column(nullable=False, default=1024)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
