from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class FacePhotoRead(BaseModel):
    id: str
    tag_id: str
    face_photo_url: str
    frame_index: int
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
