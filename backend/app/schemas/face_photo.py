from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class FacePhotoRead(BaseModel):
    id: str
    tag_id: str
    face_photo_url: str
    frame_index: int
    classification_status: str = "pending"
    classification_error: str | None = None
    classification_model: str | None = None
    classified_at: datetime | None = None
    gender: str | None = None
    ethnicity: str | None = None
    age_estimate: int | None = None
    age_range: str | None = None
    beauty_percentile: int | None = None
    beauty_level: str | None = None
    memorability_percentile: int | None = None
    memorability_level: str | None = None
    notes: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TagWithFaceRead(BaseModel):
    id: str
    name: str
    color: str | None
    owner_id: str | None
    video_count: int
    face_photo: FacePhotoRead | None

    model_config = {"from_attributes": True}
