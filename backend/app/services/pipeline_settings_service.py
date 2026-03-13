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
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(row, field, value)
    await session.commit()
    await session.refresh(row)
    return row
