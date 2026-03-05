import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Integer, String, Text, JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DailyGeneration(Base):
    __tablename__ = "daily_generations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(index=True, nullable=False)
    account_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), index=True, nullable=True)
    template_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), index=True, nullable=True)
    target_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Status lifecycle: pending → generating → reviewing → pending_publish → published
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)

    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    image: Mapped[str] = mapped_column(Text, nullable=False)
    duration: Mapped[str] = mapped_column(String(50), nullable=False)
    shots: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Result fields (filled after generation completes)
    # Stores up to 3 candidate videos: [{"video_url": "...", "thumbnail_url": "..."}, ...]
    result_videos: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # The video URL the user selected during review
    selected_video_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
