"""
回填 video_tasks.cta：按 account.product_code_mode 决定。

新版 video_task 创建时已自动按 account.product_code_mode 写入 cta，但迁移
g022 之前已有的 video_task.cta 默认全是 False。本脚本扫描所有 task，
account.product_code_mode == 'with_code' 的 task 改为 cta=True。

用法：
    cd backend

    # 预览（只统计，不改 DB）
    uv run python scripts/backfill_video_task_cta.py --dry-run

    # 实际回填
    uv run python scripts/backfill_video_task_cta.py
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, update  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models.account import Account  # noqa: E402
from app.models.video_task import VideoTask  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scripts.backfill_video_task_cta")


async def _run(*, dry_run: bool) -> None:
    async with SessionLocal() as session:
        with_code_account_ids = list((await session.execute(
            select(Account.id).where(Account.product_code_mode == "with_code")
        )).scalars().all())
        logger.info("with_code 账号数: %d", len(with_code_account_ids))

        without_code_account_ids = list((await session.execute(
            select(Account.id).where(Account.product_code_mode == "without_code")
        )).scalars().all())
        logger.info("without_code 账号数: %d", len(without_code_account_ids))

        # 需要把 cta 改为 True 的 task：account 是 with_code 但 task.cta 现在是 False
        to_true_count = await session.scalar(
            select(__import__("sqlalchemy").func.count(VideoTask.id))
            .where(VideoTask.account_id.in_(with_code_account_ids))
            .where(VideoTask.cta.is_(False))
        ) if with_code_account_ids else 0

        # 需要把 cta 改为 False 的 task：account 是 without_code 但 task.cta 现在是 True（罕见但兜底）
        to_false_count = await session.scalar(
            select(__import__("sqlalchemy").func.count(VideoTask.id))
            .where(VideoTask.account_id.in_(without_code_account_ids))
            .where(VideoTask.cta.is_(True))
        ) if without_code_account_ids else 0

        logger.info("需要改 cta False→True 的 task: %d", to_true_count or 0)
        logger.info("需要改 cta True→False 的 task: %d", to_false_count or 0)

        if dry_run:
            logger.info("[DRY-RUN] 未实际修改 DB")
            return

        if with_code_account_ids:
            await session.execute(
                update(VideoTask)
                .where(VideoTask.account_id.in_(with_code_account_ids))
                .where(VideoTask.cta.is_(False))
                .values(cta=True)
            )
        if without_code_account_ids:
            await session.execute(
                update(VideoTask)
                .where(VideoTask.account_id.in_(without_code_account_ids))
                .where(VideoTask.cta.is_(True))
                .values(cta=False)
            )
        await session.commit()
        logger.info("已落库")


async def main() -> None:
    parser = argparse.ArgumentParser(description="按 account.product_code_mode 回填 video_tasks.cta")
    parser.add_argument("--dry-run", action="store_true", help="只统计，不修改 DB")
    args = parser.parse_args()
    await _run(dry_run=args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())
