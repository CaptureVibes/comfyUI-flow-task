from __future__ import annotations

from enum import StrEnum


class TaskStatus(StrEnum):
    pending = "pending"
    running = "running"
    success = "success"
    fail = "fail"
    cancelled = "cancelled"


class PhotoSourceType(StrEnum):
    img_url = "img_url"
    upload = "upload"
    paste = "paste"


class VideoAIProcessStatus(StrEnum):
    pending = "pending"
    understanding = "understanding"
    success = "success"
    fail = "fail"
    paused = "paused"
