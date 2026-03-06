from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ComfyUISettingsPayload(BaseModel):
    server_ip: str = Field(min_length=1, max_length=255)
    ports: list[int] = Field(default_factory=list)


class ComfyUIPortStatusItem(BaseModel):
    port: int
    base_url: str
    reachable: bool
    level: str
    running_count: int = 0
    pending_count: int = 0
    error: str | None = None


class ComfyUIPortsStatusResponse(BaseModel):
    server_ip: str
    refreshed_at: datetime
    items: list[ComfyUIPortStatusItem] = Field(default_factory=list)


class SystemSettingsPayload(BaseModel):
    comfyui_server_ip: str = ""
    comfyui_ports: list[int] = Field(default_factory=list)
    evolink_api_key: str = ""
    evolink_api_base_url: str = "https://api.evolink.ai"


class PipelineSettingsPayload(BaseModel):
    understand_model: str = ""
    understand_prompt: str = ""
    understand_temperature: float = 0.3
    understand_output_format: str = "text"
    understand_json_schema: str = ""
    # 第二阶段：抽帧生图（Nano2）
    imagegen_model: str = "gemini-3.1-flash-image-preview"
    imagegen_prompt: str = ""
    imagegen_size: str = "9:16"
    imagegen_quality: str = "2K"
    # 第三阶段：拆分图片（Segment API）
    splitting_api_url: str = "http://34.21.127.95:8080"
    # 第四阶段：去脸（Face Removing API）
    face_removing_api_url: str = "http://34.86.216.234:8001"
    face_removing_score_thresh: float = 0.3
    face_removing_margin_scale: float = 0.2
    face_removing_head_top_ratio: float = 0.7
    # 第五阶段：图片超分（Pillow LANCZOS）
    upscaling_scale: int = 1024
