"""
数据修复脚本：为数据库中重复的账号名自动追加 -1、-2 后缀

用法：
    cd backend
    uv run python scripts/dedup_account_names.py

特性：
- 幂等：只处理有重名的账号，已唯一的跳过
- 按 created_at 升序保留最早的那条原名，后续重名追加后缀
- dry_run 模式（默认开启）：只打印变更，不写库，确认无误后加 --apply 实际执行
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, func

from app.db.session import SessionLocal
from app.models.account import Account

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


async def _unique_name(taken: set[str], base_name: str) -> str:
    """在 taken 集合中找一个不重复的名字。"""
    if base_name not in taken:
        return base_name
    suffix = 1
    while True:
        candidate = f"{base_name}-{suffix}"
        if candidate not in taken:
            return candidate
        suffix += 1


async def run(dry_run: bool = True) -> None:
    async with SessionLocal() as session:
        # 找出所有有重名的账号名
        dup_stmt = (
            select(Account.account_name)
            .group_by(Account.account_name)
            .having(func.count(Account.id) > 1)
        )
        dup_names = {row[0] for row in (await session.execute(dup_stmt)).all()}

        if not dup_names:
            logger.info("没有重复账号名，无需处理。")
            return

        logger.info("发现 %d 个重复账号名：%s", len(dup_names), dup_names)

        # 已占用的名字（全量，用于冲突检查）
        all_names_result = await session.execute(select(Account.account_name))
        taken: set[str] = {row[0] for row in all_names_result.all()}

        changes: list[tuple[Account, str, str]] = []  # (account, old_name, new_name)

        for dup_name in sorted(dup_names):
            # 按创建时间升序，最早的保留原名
            stmt = (
                select(Account)
                .where(Account.account_name == dup_name)
                .order_by(Account.created_at.asc())
            )
            accounts = list((await session.execute(stmt)).scalars().all())

            # 第一条保留原名
            taken.add(accounts[0].account_name)

            for acc in accounts[1:]:
                old_name = acc.account_name
                new_name = await _unique_name(taken, old_name)
                taken.add(new_name)
                changes.append((acc, old_name, new_name))

        if not changes:
            logger.info("无需修改。")
            return

        logger.info("\n--- 变更列表 (dry_run=%s) ---", dry_run)
        for acc, old, new in changes:
            logger.info("  账号 %s: %r → %r", acc.id, old, new)

        if dry_run:
            logger.info("\n[dry_run] 未写入数据库。加 --apply 参数实际执行。")
            return

        for acc, old, new in changes:
            acc.account_name = new

        await session.commit()
        logger.info("\n已更新 %d 条记录。", len(changes))


if __name__ == "__main__":
    apply = "--apply" in sys.argv
    asyncio.run(run(dry_run=not apply))
