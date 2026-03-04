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


class EvoLinkSettingsPayload(BaseModel):
    api_key: str = ""
    api_base_url: str = "https://api.evolink.ai"
    # 步骤一：视频整体理解
    understand_model: str = ""
    understand_prompt: str = ""
    understand_temperature: float = 0.3
    understand_output_format: str = "text"
    understand_json_schema: str = ""
