from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_setting import SystemSetting

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
