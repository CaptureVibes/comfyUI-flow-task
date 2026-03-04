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
    row.extract_model = payload.extract_model
    row.extract_prompt = payload.extract_prompt
    row.extract_temperature = payload.extract_temperature
    row.extract_output_format = payload.extract_output_format
    row.extract_json_schema = payload.extract_json_schema
    row.image_gen_model = payload.image_gen_model
    row.image_gen_prompt_template = payload.image_gen_prompt_template
    row.image_gen_size = payload.image_gen_size
    row.image_gen_quality = payload.image_gen_quality
    await session.commit()
    await session.refresh(row)
    return row
