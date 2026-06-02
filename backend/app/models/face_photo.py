from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FacePhoto(Base):
    __tablename__ = "face_photos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    face_photo_url: Mapped[str] = mapped_column(Text, nullable=False)
    frame_index: Mapped[int] = mapped_column(Integer, nullable=False)
    classification_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    classification_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    classification_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    classification_raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    classified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ethnicity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    age_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    age_range: Mapped[str | None] = mapped_column(String(20), nullable=True)
    beauty_percentile: Mapped[int | None] = mapped_column(Integer, nullable=True)
    beauty_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    memorability_percentile: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memorability_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
