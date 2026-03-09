import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, JSON, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class VideoTask(Base):
    __tablename__ = "video_tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(index=True, nullable=False)
    account_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), index=True, nullable=True)
    template_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), index=True, nullable=True)
    target_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)

    # Status lifecycle: pending → generating → reviewing → pending_publish → published
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)

    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    duration: Mapped[str] = mapped_column(String(50), nullable=False)
    shots: Mapped[list | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    sub_tasks: Mapped[list["VideoSubTask"]] = relationship(
        "VideoSubTask",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="VideoSubTask.sub_index",
    )


class VideoSubTask(Base):
    __tablename__ = "video_sub_tasks"
    __table_args__ = (
        UniqueConstraint("task_id", "sub_index", name="uq_video_sub_tasks_task_sub_index"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("video_tasks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    sub_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Status lifecycle: pending → generating → reviewing → pending_publish → published
    # abandoned: user selected another sub-task, this one is discarded
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)

    # CDN URL written after fetch-results; sub-task UUID is used as video_id in GCS path
    result_video_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # AI scoring: two-round scoring with final weighted score
    ai_score: Mapped[float | None] = mapped_column(Integer, nullable=True)  # Final score 0-100
    round1_score: Mapped[float | None] = mapped_column(Integer, nullable=True)
    round2_score: Mapped[float | None] = mapped_column(Integer, nullable=True)
    round1_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    round2_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Error message when AI scoring fails
    scoring_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # True when this sub-task's video was chosen by the user for publishing
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    task: Mapped["VideoTask"] = relationship("VideoTask", back_populates="sub_tasks")
