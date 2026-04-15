"""
查询 account_channel_reservations 表中已绑定的所有 channel_id，打印为 JSON 数组。

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
from app.models.account_channel_reservation import AccountChannelReservation


async def main() -> None:
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(AccountChannelReservation.channel_id)
                .where(AccountChannelReservation.status == "bound")
                .where(AccountChannelReservation.channel_id.isnot(None))
            )
        ).scalars().all()

    channel_ids = [str(cid) for cid in rows if cid]
    print(json.dumps(channel_ids, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
