from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenData, require_current_user
from app.db.session import get_db
from app.schemas.settings import (
    CandidateConfigPayload,
    PipelineSettingsPayload,
)
from app.schemas.topic import KeywordGenConfigPayload
from app.services.channel_status_poller import run_channel_status_check
from app.services.pipeline_settings_service import get_or_create_pipeline_settings, update_pipeline_settings
from app.services.system_settings_service import get_or_create_system_settings

router = APIRouter(prefix="/settings", tags=["settings"])


# ---------------------------------------------------------------------------
# System settings (global, single-row)
# ---------------------------------------------------------------------------

class SystemSettingsPayload(BaseModel):
    use_seedance_api: bool = False


@router.get("/system", response_model=SystemSettingsPayload)
async def get_system_settings(
    token: TokenData = Depends(require_current_user),
    session: AsyncSession = Depends(get_db),
) -> SystemSettingsPayload:
    row = await get_or_create_system_settings(session)
    return SystemSettingsPayload(use_seedance_api=row.use_seedance_api)


@router.put("/system", response_model=SystemSettingsPayload)
async def put_system_settings(
    payload: SystemSettingsPayload,
    token: TokenData = Depends(require_current_user),
    session: AsyncSession = Depends(get_db),
) -> SystemSettingsPayload:
    row = await get_or_create_system_settings(session)
    row.use_seedance_api = payload.use_seedance_api
    await session.commit()
    await session.refresh(row)
    return SystemSettingsPayload(use_seedance_api=row.use_seedance_api)


# ---------------------------------------------------------------------------
# 手动触发频道状态检查
# ---------------------------------------------------------------------------

@router.post("/check-channel-status")
async def trigger_check_channel_status(
    token: TokenData = Depends(require_current_user),
) -> dict:
    """立即执行一次频道授权状态检查（通常每天北京时间 10:00 自动触发）。"""
    result = await run_channel_status_check()
    return {"status": "ok", "checked": result["checked"], "changed": result["changed"]}


# ---------------------------------------------------------------------------
# Pipeline settings (per-user)
# ---------------------------------------------------------------------------

@router.get("/pipeline", response_model=PipelineSettingsPayload)
async def get_pipeline_settings(
    token: TokenData = Depends(require_current_user),
    session: AsyncSession = Depends(get_db),
) -> PipelineSettingsPayload:
    row = await get_or_create_pipeline_settings(session, owner_id=token.user_id)
    return PipelineSettingsPayload(
        understand_model=row.understand_model,
        understand_prompt=row.understand_prompt,
        understand_temperature=row.understand_temperature,
        imagegen_model=row.imagegen_model,
        imagegen_prompt=row.imagegen_prompt,
        imagegen_size=row.imagegen_size,
        imagegen_quality=row.imagegen_quality,
        splitting_api_url=row.splitting_api_url,
        face_removing_api_url=row.face_removing_api_url,
        face_removing_score_thresh=row.face_removing_score_thresh,
        face_removing_margin_scale=row.face_removing_margin_scale,
        face_removing_head_top_ratio=row.face_removing_head_top_ratio,
        upscaling_scale=row.upscaling_scale,
        ai_account_analysis_sample_size=row.ai_account_analysis_sample_size,
        ai_account_video_prompt=row.ai_account_video_prompt,
        ai_account_video_model=row.ai_account_video_model,
        ai_account_name_prompt=row.ai_account_name_prompt,
        ai_account_avatar_prompt=row.ai_account_avatar_prompt,
        ai_account_photo_image_prompt=row.ai_account_photo_image_prompt,
        ai_account_painting_prompt=row.ai_account_painting_prompt,
        ai_account_name_model=row.ai_account_name_model,
        ai_account_avatar_model=row.ai_account_avatar_model,
        ai_account_avatar_size=row.ai_account_avatar_size,
        ai_account_avatar_quality=row.ai_account_avatar_quality,
        keyword_gen_model=row.keyword_gen_model,
        keyword_gen_prompt=row.keyword_gen_prompt,
        keyword_gen_count=row.keyword_gen_count,
        keyword_gen_temperature=row.keyword_gen_temperature,
        face_select_model=row.face_select_model,
        face_select_prompt=row.face_select_prompt,
        ai_account_exclusive_name_prompt=row.ai_account_exclusive_name_prompt,
        ai_account_shared_name_prompt=row.ai_account_shared_name_prompt,
        hashtag_search_top_n=row.hashtag_search_top_n,
        hashtag_filter_model=row.hashtag_filter_model,
        hashtag_filter_prompt=row.hashtag_filter_prompt,
    )


@router.put("/pipeline", response_model=PipelineSettingsPayload)
async def put_pipeline_settings(
    payload: PipelineSettingsPayload,
    token: TokenData = Depends(require_current_user),
    session: AsyncSession = Depends(get_db),
) -> PipelineSettingsPayload:
    row = await update_pipeline_settings(session, owner_id=token.user_id, payload=payload)
    return PipelineSettingsPayload(
        understand_model=row.understand_model,
        understand_prompt=row.understand_prompt,
        understand_temperature=row.understand_temperature,
        imagegen_model=row.imagegen_model,
        imagegen_prompt=row.imagegen_prompt,
        imagegen_size=row.imagegen_size,
        imagegen_quality=row.imagegen_quality,
        splitting_api_url=row.splitting_api_url,
        face_removing_api_url=row.face_removing_api_url,
        face_removing_score_thresh=row.face_removing_score_thresh,
        face_removing_margin_scale=row.face_removing_margin_scale,
        face_removing_head_top_ratio=row.face_removing_head_top_ratio,
        upscaling_scale=row.upscaling_scale,
        ai_account_analysis_sample_size=row.ai_account_analysis_sample_size,
        ai_account_video_prompt=row.ai_account_video_prompt,
        ai_account_video_model=row.ai_account_video_model,
        ai_account_name_prompt=row.ai_account_name_prompt,
        ai_account_avatar_prompt=row.ai_account_avatar_prompt,
        ai_account_photo_image_prompt=row.ai_account_photo_image_prompt,
        ai_account_painting_prompt=row.ai_account_painting_prompt,
        ai_account_name_model=row.ai_account_name_model,
        ai_account_avatar_model=row.ai_account_avatar_model,
        ai_account_avatar_size=row.ai_account_avatar_size,
        ai_account_avatar_quality=row.ai_account_avatar_quality,
        keyword_gen_model=row.keyword_gen_model,
        keyword_gen_prompt=row.keyword_gen_prompt,
        keyword_gen_count=row.keyword_gen_count,
        keyword_gen_temperature=row.keyword_gen_temperature,
        face_select_model=row.face_select_model,
        face_select_prompt=row.face_select_prompt,
        ai_account_exclusive_name_prompt=row.ai_account_exclusive_name_prompt,
        ai_account_shared_name_prompt=row.ai_account_shared_name_prompt,
        hashtag_search_top_n=row.hashtag_search_top_n,
        hashtag_filter_model=row.hashtag_filter_model,
        hashtag_filter_prompt=row.hashtag_filter_prompt,
    )


# ---------------------------------------------------------------------------
# Keyword generation config (per-user, isolated save)
# ---------------------------------------------------------------------------

@router.get("/keyword-gen-config", response_model=KeywordGenConfigPayload)
async def get_keyword_gen_config(
    token: TokenData = Depends(require_current_user),
    session: AsyncSession = Depends(get_db),
) -> KeywordGenConfigPayload:
    row = await get_or_create_pipeline_settings(session, owner_id=token.user_id)
    return KeywordGenConfigPayload(
        keyword_gen_model=row.keyword_gen_model,
        keyword_gen_prompt=row.keyword_gen_prompt,
        keyword_gen_count=row.keyword_gen_count,
        keyword_gen_temperature=row.keyword_gen_temperature,
    )


@router.put("/keyword-gen-config", response_model=KeywordGenConfigPayload)
async def put_keyword_gen_config(
    payload: KeywordGenConfigPayload,
    token: TokenData = Depends(require_current_user),
    session: AsyncSession = Depends(get_db),
) -> KeywordGenConfigPayload:
    row = await get_or_create_pipeline_settings(session, owner_id=token.user_id)
    updates = payload.model_dump(exclude_none=True)
    for field, value in updates.items():
        setattr(row, field, value)
    await session.commit()
    await session.refresh(row)
    return KeywordGenConfigPayload(
        keyword_gen_model=row.keyword_gen_model,
        keyword_gen_prompt=row.keyword_gen_prompt,
        keyword_gen_count=row.keyword_gen_count,
        keyword_gen_temperature=row.keyword_gen_temperature,
    )


# ---------------------------------------------------------------------------
# 候选库配置（per-user，独立保存）
# ---------------------------------------------------------------------------

@router.get("/candidate-config", response_model=CandidateConfigPayload)
async def get_candidate_config(
    token: TokenData = Depends(require_current_user),
    session: AsyncSession = Depends(get_db),
) -> CandidateConfigPayload:
    row = await get_or_create_pipeline_settings(session, owner_id=token.user_id)
    return CandidateConfigPayload(
        candidate_max_bloggers=row.candidate_max_bloggers,
        candidate_exclusive_threshold=row.candidate_exclusive_threshold,
        candidate_max_videos_per_blogger=row.candidate_max_videos_per_blogger,
        candidate_max_duration_seconds=row.candidate_max_duration_seconds,
        candidate_retry_delay_seconds=row.candidate_retry_delay_seconds,
        candidate_min_play_count=row.candidate_min_play_count,
        candidate_publish_after_date=row.candidate_publish_after_date,
        candidate_shared_top_n=row.candidate_shared_top_n,
        candidate_ai_review_enabled=row.candidate_ai_review_enabled,
        candidate_ai_review_model=row.candidate_ai_review_model,
        candidate_ai_review_prompt=row.candidate_ai_review_prompt,
        candidate_schedule_enabled=row.candidate_schedule_enabled,
        candidate_schedule_cron=row.candidate_schedule_cron,
    )


@router.put("/candidate-config", response_model=CandidateConfigPayload)
async def put_candidate_config(
    payload: CandidateConfigPayload,
    token: TokenData = Depends(require_current_user),
    session: AsyncSession = Depends(get_db),
) -> CandidateConfigPayload:
    row = await get_or_create_pipeline_settings(session, owner_id=token.user_id)
    row.candidate_max_bloggers = payload.candidate_max_bloggers
    row.candidate_exclusive_threshold = payload.candidate_exclusive_threshold
    row.candidate_max_videos_per_blogger = payload.candidate_max_videos_per_blogger
    row.candidate_max_duration_seconds = payload.candidate_max_duration_seconds
    row.candidate_retry_delay_seconds = payload.candidate_retry_delay_seconds
    row.candidate_min_play_count = payload.candidate_min_play_count
    row.candidate_publish_after_date = payload.candidate_publish_after_date
    row.candidate_shared_top_n = payload.candidate_shared_top_n
    row.candidate_ai_review_enabled = payload.candidate_ai_review_enabled
    row.candidate_ai_review_model = payload.candidate_ai_review_model
    row.candidate_ai_review_prompt = payload.candidate_ai_review_prompt
    row.candidate_schedule_enabled = payload.candidate_schedule_enabled
    row.candidate_schedule_cron = payload.candidate_schedule_cron
    await session.commit()
    await session.refresh(row)
    return CandidateConfigPayload(
        candidate_max_bloggers=row.candidate_max_bloggers,
        candidate_exclusive_threshold=row.candidate_exclusive_threshold,
        candidate_max_videos_per_blogger=row.candidate_max_videos_per_blogger,
        candidate_max_duration_seconds=row.candidate_max_duration_seconds,
        candidate_retry_delay_seconds=row.candidate_retry_delay_seconds,
        candidate_min_play_count=row.candidate_min_play_count,
        candidate_publish_after_date=row.candidate_publish_after_date,
        candidate_shared_top_n=row.candidate_shared_top_n,
        candidate_ai_review_enabled=row.candidate_ai_review_enabled,
        candidate_ai_review_model=row.candidate_ai_review_model,
        candidate_ai_review_prompt=row.candidate_ai_review_prompt,
        candidate_schedule_enabled=row.candidate_schedule_enabled,
        candidate_schedule_cron=row.candidate_schedule_cron,
    )
