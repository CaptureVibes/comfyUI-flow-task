from __future__ import annotations

import json
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


def _json_serializer(obj):
    return json.dumps(obj, ensure_ascii=False)


engine = create_async_engine(
    settings.database_url,
    future=True,
    pool_pre_ping=True,
    json_serializer=_json_serializer,
)
SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
