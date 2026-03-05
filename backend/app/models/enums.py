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
    understanding = "understanding"   # 阶段1：AI 视频理解
    imagegen = "imagegen"             # 阶段2：抽帧生图
    splitting = "splitting"           # 阶段3：拆分图片
    face_removing = "face_removing"   # 阶段4：消除人脸
    success = "success"
    fail = "fail"
    paused = "paused"
