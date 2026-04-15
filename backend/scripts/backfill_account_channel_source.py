"""
数据回填脚本：为 accounts.social_bindings 里缺少 channel_source 的条目补 "openapi"

背景：
    引入外部频道（ext_pub）前创建的账号，social_bindings 里没有 channel_source 字段。
    历史数据全部是内部频道，统一补 "openapi"。

处理逻辑（幂等）：
    - 跳过所有 binding 都已有 channel_source 的账号
    - 只修改缺失 channel_source 的条目，其余字段不动

用法：
    cd backend
    uv run python scripts/backfill_account_channel_source.py [--dry-run]
"""
from __future__ import annotations

import asyncio
import argparse
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.account import Account

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_account_channel_source")

BATCH_SIZE = 100


async def backfill(dry_run: bool = False) -> None:
    updated_accounts = 0
    updated_bindings = 0
    skipped = 0
    total = 0

    async with SessionLocal() as db:
        rows = (await db.execute(select(Account))).scalars().all()

    logger.info("共找到 %d 个账号", len(rows))

    batch: list[Account] = []

    for account in rows:
        total += 1
        bindings: list[dict] = account.social_bindings or []
        if not bindings:
            skipped += 1
            continue

        # 检查是否有需要补的条目
        needs_update = any(
            isinstance(b, dict) and "channel_source" not in b
            for b in bindings
        )
        if not needs_update:
            skipped += 1
            continue

        new_bindings = []
        count = 0
        for b in bindings:
            if isinstance(b, dict) and "channel_source" not in b:
                b = {**b, "channel_source": "openapi"}
                count += 1
            new_bindings.append(b)

        logger.info(
            "[%s] account=%s (%s) → 补 channel_source 的 binding 数=%d，bindings=%s",
            "DRY" if dry_run else "UPD",
            account.id, account.account_name, count, new_bindings,
        )

        if not dry_run:
            account.social_bindings = new_bindings
            batch.append(account)

        updated_accounts += 1
        updated_bindings += count

        if not dry_run and len(batch) >= BATCH_SIZE:
            async with SessionLocal() as db:
                for a in batch:
                    await db.merge(a)
                await db.commit()
            logger.info("已提交 %d 个账号", len(batch))
            batch.clear()

    if not dry_run and batch:
        async with SessionLocal() as db:
            for a in batch:
                await db.merge(a)
            await db.commit()
        logger.info("已提交剩余 %d 个账号", len(batch))

    logger.info(
        "完成：总计 %d 个账号，更新 %d 个（%d 条 binding），跳过 %d 个%s",
        total, updated_accounts, updated_bindings, skipped,
        "（dry-run，未写入）" if dry_run else "",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="回填 social_bindings.channel_source 字段")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写入数据库")
    args = parser.parse_args()
    asyncio.run(backfill(dry_run=args.dry_run))
