from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_setting import SystemSetting
from app.schemas.settings import SystemSettingsPayload

_DEFAULT_KEY = "default"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def get_or_create_system_settings(session: AsyncSession) -> SystemSetting:
    row = await session.scalar(select(SystemSetting).where(SystemSetting.key == _DEFAULT_KEY))
    if row is None:
        now = _utcnow()
        row = SystemSetting(key=_DEFAULT_KEY, created_at=now, updated_at=now)
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


async def update_system_settings(session: AsyncSession, payload: SystemSettingsPayload) -> SystemSetting:
    row = await get_or_create_system_settings(session)
    row.comfyui_server_ip = payload.comfyui_server_ip
    row.comfyui_ports = payload.comfyui_ports
    row.evolink_api_key = payload.evolink_api_key
    row.evolink_api_base_url = payload.evolink_api_base_url
    await session.commit()
    await session.refresh(row)
    return row
