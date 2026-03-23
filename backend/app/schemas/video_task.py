import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict
from app.schemas.video_ai_template import TagRead
from app.schemas.video_ai_template import VideoSourceSummary


class VideoTaskCreate(BaseModel):
    account_id: uuid.UUID
    template_id: uuid.UUID
    final_prompt: str
    duration: str
    shots: list | None = None


class VideoSubTaskRead(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    sub_index: int
    status: str
    result_video_url: str | None = None
    selected: bool
    ai_score: int | None = None  # Final AI score 0-100
    round1_score: int | None = None
    round2_score: int | None = None
    round1_reason: str | None = None
    round2_reason: str | None = None
    scoring_error: str | None = None  # Error message when AI scoring fails
    manual_score: int | None = None  # User-written score (0-100)
    manual_note: str | None = None   # User-written note, independent of AI scoring
    elsa_score: int | None = None    # Elsa review score (0-100)
    temporal_consistency: bool | None = None
    character_integrity: bool | None = None
    audio_sync: bool | None = None
    critical_fail: bool | None = None
    dimension_scores: dict | None = None
    weighted_total_score: float | None = None
    queue_order: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class VideoTaskRead(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    account_id: uuid.UUID | None = None
    template_id: uuid.UUID | None = None
    target_date: date
    status: str
    prompt: str
    duration: str
    shots: list | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class VideoTaskDetailRead(VideoTaskRead):
    sub_tasks: list[VideoSubTaskRead] = []
    account_name: str | None = None
    template_title: str | None = None
    tags: list[TagRead] = []
    original_video: VideoSourceSummary | None = None


class VideoTaskListItem(VideoTaskDetailRead):
    """Enriched list item with denormalized account/template names and sub-task progress."""
    sub_tasks_done: int = 0  # number of sub-tasks with result_video_url set


class VideoTaskListPage(BaseModel):
    items: list[VideoTaskListItem]
    total: int
    page: int
    page_size: int


class VideoSubTaskStatusUpdate(BaseModel):
    status: str
    result_video_url: str | None = None
    # When selecting a video for publishing: set selected=True to trigger
    # pending_publish transition and abandon the other two sub-tasks
    selected: bool | None = None


class VideoSubTaskNoteUpdate(BaseModel):
    manual_score: int | None = None
    manual_note: str | None = None
    elsa_score: int | None = None
    temporal_consistency: bool | None = None
    character_integrity: bool | None = None
    audio_sync: bool | None = None
    dimension_scores: dict | None = None


class VideoSubTaskStateRead(BaseModel):
    id: uuid.UUID
    status: str
    result_video_url: str | None = None
    ai_score: int | None = None
    round1_score: int | None = None
    round2_score: int | None = None
    round1_reason: str | None = None
    round2_reason: str | None = None
    scoring_error: str | None = None

    model_config = ConfigDict(from_attributes=True)


class VideoTaskStateRead(BaseModel):
    id: uuid.UUID
    status: str
    sub_tasks: list[VideoSubTaskStateRead] = []

    model_config = ConfigDict(from_attributes=True)


class TaskNavItem(BaseModel):
    id: uuid.UUID
    status: str
    account_id: uuid.UUID | None = None
    account_name: str | None = None


class VideoTaskNavRead(BaseModel):
    position: int        # 0-based index in account task list (DESC by created_at)
    total: int           # total tasks for this account
    selected_count: int  # tasks with pending_publish/queued/publishing/published status
    prev_task: TaskNavItem | None = None
    next_task: TaskNavItem | None = None
    prev_blogger_task: TaskNavItem | None = None
    next_blogger_task: TaskNavItem | None = None
