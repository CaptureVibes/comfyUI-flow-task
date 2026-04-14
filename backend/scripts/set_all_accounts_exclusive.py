"""
将数据库中所有账号的 account_type 设置为 'exclusive'

用法：
    uv run python scripts/set_all_accounts_exclusive.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.db.session import SessionLocal
from sqlalchemy import text


async def main() -> None:
    async with SessionLocal() as db:
        result = await db.execute(text("UPDATE accounts SET account_type = 'exclusive'"))
        await db.commit()
        print(f"Done: updated {result.rowcount} rows to exclusive")


if __name__ == "__main__":
    asyncio.run(main())
