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
    understanding = "understanding"       # 阶段1：AI 视频理解
    imagegen = "imagegen"                 # 阶段2：抽帧并上传CDN
    outfit_selecting = "outfit_selecting" # 阶段2b：Gemini 识别 Unique 穿搭
    lookbook_gen = "lookbook_gen"         # 阶段2.5：对每个 outfit_shot 生成 4×2 八拼图并切割
    remixing = "remixing"                 # 阶段2.5 之后：用户触发某次重洗，正在跑下游
    outfit_detailing = "outfit_detailing" # 阶段3a：理解每个穿搭的单品
    product_imagegen = "product_imagegen" # 阶段3b：生成单品图
    outfit_regen = "outfit_regen"         # 阶段3c：生成新造型图
    splitting = "splitting"               # 阶段3（旧）：拆分图片（保留兼容）
    face_removing = "face_removing"       # 阶段4：消除人脸
    upscaling = "upscaling"               # 阶段5：图片超分
    success = "success"
    fail = "fail"
    paused = "paused"
