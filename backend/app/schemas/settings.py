from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CandidateConfigPayload(BaseModel):
    candidate_max_bloggers: int = 20
    candidate_exclusive_threshold: int = 10
    candidate_max_videos_per_blogger: int = 100
    candidate_max_duration_seconds: int = 30
    candidate_retry_delay_seconds: int = 5
    candidate_min_play_count: int = 0
    candidate_publish_after_date: str | None = None
    candidate_shared_top_n: int = 50
    candidate_ai_review_enabled: bool = False
    candidate_ai_review_model: str = "gemini-3.1-pro-preview"
    candidate_ai_review_prompt: str = ""
    candidate_schedule_enabled: bool = False
    candidate_schedule_cron: str | None = None
    candidate_search_interval_minutes: int = 0


class CandidateSearchPayload(BaseModel):
    keyword_text: str
    keyword_id: str | None = None  # UUID 字符串，可选（手动输入时为空）


class CandidateVideoItem(BaseModel):
    id: str
    keyword_id: str | None
    keyword_text: str
    template_type: str
    blogger_unique_id: str
    blogger_nickname: str | None
    blogger_follower_count: int | None
    video_id: str
    video_url: str | None
    video_title: str | None
    duration: int | None
    cover_url: str | None
    cdn_cover_url: str | None
    play_count: int | None
    like_count: int | None
    video_source_id: str | None = None
    status: str = "pending"
    ai_reviewed: bool = False
    ai_error: str | None = None
    created_at: datetime


class CandidateVideoListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[CandidateVideoItem]


class PipelineSettingsPayload(BaseModel):
    understand_model: str = ""
    understand_prompt: str = ""
    understand_temperature: float = 0.3
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
    # AI 账号生成配置
    ai_account_analysis_sample_size: int = 10
    ai_account_video_prompt: str = ""
    ai_account_video_model: str = "gemini-3.1-pro-preview"
    ai_account_name_prompt: str = ""
    ai_account_avatar_prompt: str = ""
    ai_account_photo_image_prompt: str = ""
    ai_account_painting_prompt: str = ""
    ai_account_name_model: str = "gemini-3.1-pro-preview"
    ai_account_avatar_model: str = "gemini-3.1-flash-image-preview"
    ai_account_avatar_size: str = "1:1"
    ai_account_avatar_quality: str = "1K"
    # 关键词生成配置
    keyword_gen_model: str = "gemini-3.1-pro-preview"
    keyword_gen_prompt: str = ""
    keyword_gen_count: int = 50
    keyword_gen_temperature: float = 0.7
    # 人脸选择配置
    face_select_model: str = "gemini-3.1-pro-preview"
    face_select_prompt: str = ""


class CandidateBatchAIReviewRequest(BaseModel):
    ids: list[str]


class CandidateBatchImportRequest(BaseModel):
    ids: list[str]
