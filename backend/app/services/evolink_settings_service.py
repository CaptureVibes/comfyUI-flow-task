from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evolink_setting import EvoLinkSetting
from app.schemas.settings import EvoLinkSettingsPayload

_DEFAULT_KEY = "default"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def get_or_create_evolink_settings(session: AsyncSession) -> EvoLinkSetting:
    row = await session.scalar(select(EvoLinkSetting).where(EvoLinkSetting.key == _DEFAULT_KEY))
    if row is None:
        now = _utcnow()
        row = EvoLinkSetting(key=_DEFAULT_KEY, created_at=now, updated_at=now)
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


async def update_evolink_settings(session: AsyncSession, payload: EvoLinkSettingsPayload) -> EvoLinkSetting:
    row = await get_or_create_evolink_settings(session)
    row.api_key = payload.api_key
    row.api_base_url = payload.api_base_url
    row.understand_model = payload.understand_model
    row.understand_prompt = payload.understand_prompt
    row.understand_temperature = payload.understand_temperature
    row.understand_output_format = payload.understand_output_format
    row.understand_json_schema = payload.understand_json_schema
    await session.commit()
    await session.refresh(row)
    return row
