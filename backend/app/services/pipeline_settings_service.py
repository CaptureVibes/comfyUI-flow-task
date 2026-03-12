from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline_setting import PipelineSetting
from app.schemas.settings import PipelineSettingsPayload


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def get_or_create_pipeline_settings(session: AsyncSession, owner_id: uuid.UUID) -> PipelineSetting:
    row = await session.scalar(select(PipelineSetting).where(PipelineSetting.owner_id == owner_id))
    if row is None:
        now = _utcnow()
        row = PipelineSetting(owner_id=owner_id, created_at=now, updated_at=now)
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


async def update_pipeline_settings(session: AsyncSession, owner_id: uuid.UUID, payload: PipelineSettingsPayload) -> PipelineSetting:
    row = await get_or_create_pipeline_settings(session, owner_id)
    row.understand_model = payload.understand_model
    row.understand_prompt = payload.understand_prompt
    row.understand_temperature = payload.understand_temperature
    row.imagegen_model = payload.imagegen_model
    row.imagegen_prompt = payload.imagegen_prompt
    row.imagegen_size = payload.imagegen_size
    row.imagegen_quality = payload.imagegen_quality
    row.splitting_api_url = payload.splitting_api_url
    row.face_removing_api_url = payload.face_removing_api_url
    row.face_removing_score_thresh = payload.face_removing_score_thresh
    row.face_removing_margin_scale = payload.face_removing_margin_scale
    row.face_removing_head_top_ratio = payload.face_removing_head_top_ratio
    row.upscaling_scale = payload.upscaling_scale
    row.ai_account_video_prompt = payload.ai_account_video_prompt
    row.ai_account_video_model = payload.ai_account_video_model
    row.ai_account_name_prompt = payload.ai_account_name_prompt
    row.ai_account_avatar_prompt = payload.ai_account_avatar_prompt
    row.ai_account_photo_video_prompt = payload.ai_account_photo_video_prompt
    row.ai_account_photo_image_prompt = payload.ai_account_photo_image_prompt
    row.ai_account_name_model = payload.ai_account_name_model
    row.ai_account_avatar_model = payload.ai_account_avatar_model
    row.ai_account_avatar_size = payload.ai_account_avatar_size
    row.ai_account_avatar_quality = payload.ai_account_avatar_quality
    await session.commit()
    await session.refresh(row)
    return row
