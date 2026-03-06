from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evolink_setting import EvoLinkSetting
from app.schemas.settings import EvoLinkSettingsPayload


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def get_or_create_evolink_settings(session: AsyncSession, owner_id: uuid.UUID) -> EvoLinkSetting:
    row = await session.scalar(select(EvoLinkSetting).where(EvoLinkSetting.owner_id == owner_id))
    if row is None:
        now = _utcnow()
        row = EvoLinkSetting(owner_id=owner_id, created_at=now, updated_at=now)
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


async def update_evolink_settings(session: AsyncSession, owner_id: uuid.UUID, payload: EvoLinkSettingsPayload) -> EvoLinkSetting:
    row = await get_or_create_evolink_settings(session, owner_id)
    row.api_key = payload.api_key
    row.api_base_url = payload.api_base_url
    row.understand_model = payload.understand_model
    row.understand_prompt = payload.understand_prompt
    row.understand_temperature = payload.understand_temperature
    await session.commit()
    await session.refresh(row)
    return row
