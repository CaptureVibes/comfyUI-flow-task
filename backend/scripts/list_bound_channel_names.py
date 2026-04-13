"""
查询 accounts 表中已绑定的所有 channel_name，打印为 JSON 数组。

用法：
    cd backend
    uv run python scripts/list_bound_channel_names.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.account import Account


async def main() -> None:
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(Account.social_bindings).where(Account.social_bindings.isnot(None))
            )
        ).scalars().all()

    channel_names: list[str] = []
    for bindings in rows:
        if not isinstance(bindings, list):
            continue
        for binding in bindings:
            cid = binding.get("channel_id") if isinstance(binding, dict) else None
            if cid:
                channel_names.append(cid)

    print(json.dumps(channel_names, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
