"""
手动触发账号分级评估（冷启动 / 临时补跑用）

用法：
    cd backend

    # 预览：列出会被晋升为常规号的实验号，不修改 DB，也不做 dev→prod 随机晋级
    uv run python scripts/run_account_tier_evaluation.py --dry-run

    # 仅执行 test→dev 晋级（跳过 dev→prod 随机扩量），适合冷启动阶段
    uv run python scripts/run_account_tier_evaluation.py --skip-dev-to-prod

    # 执行完整两步（等同于每日定时任务）
    uv run python scripts/run_account_tier_evaluation.py

判定规则（与 account_tier_scheduler 保持一致）：
- 实验号 (test) → 常规号 (dev)：最近 7 条 completed/partial publication 均播 ≥ 700
  且过去 7 天 completed/partial 数 ≥ 6。
- 常规号 (dev) → 正式号 (prod)：random.uniform(0, 6%) * 当前 prod 数，从 dev 随机选；
  prod=0 时跳过（冷启动需先在 accounts 页面批量改为正式号）。
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func, select  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models.account import Account  # noqa: E402
from app.models.video_publication import VideoPublication  # noqa: E402
from app.models.video_task import VideoSubTask, VideoTask  # noqa: E402
from app.services.account_tier_scheduler import (  # noqa: E402
    _DEV_AVG_VIEWS_MIN,
    _DEV_LOOKBACK_DAYS,
    _DEV_LOOKBACK_VIDEOS,
    _DEV_RECENT_VIDEO_MIN,
    _evaluate_dev_to_prod,
    _evaluate_test_to_dev,
    _publication_views,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scripts.run_account_tier_evaluation")


async def _dry_run() -> None:
    """只列出符合 test→dev 条件的账号，不修改 DB。"""
    async with SessionLocal() as session:
        test_accounts = list((await session.execute(
            select(Account).where(Account.account_tier == "test")
        )).scalars().all())
        logger.info("当前实验号数量: %d", len(test_accounts))

        cutoff_recent = datetime.now(timezone.utc) - timedelta(days=_DEV_LOOKBACK_DAYS)
        candidates: list[tuple[Account, float, int]] = []
        skipped_few_pubs = 0
        skipped_low_avg = 0
        skipped_low_recent = 0

        for account in test_accounts:
            last_pubs = list((await session.execute(
                select(VideoPublication)
                .join(VideoSubTask, VideoSubTask.id == VideoPublication.sub_task_id)
                .join(VideoTask, VideoTask.id == VideoSubTask.task_id)
                .where(VideoTask.account_id == account.id)
                .where(VideoPublication.status.in_(["completed", "partial"]))
                .where(VideoPublication.completed_at.isnot(None))
                .order_by(VideoPublication.completed_at.desc())
                .limit(_DEV_LOOKBACK_VIDEOS)
            )).scalars().all())

            if len(last_pubs) < _DEV_LOOKBACK_VIDEOS:
                skipped_few_pubs += 1
                continue

            avg_views = sum(_publication_views(p) for p in last_pubs) / _DEV_LOOKBACK_VIDEOS
            if avg_views < _DEV_AVG_VIEWS_MIN:
                skipped_low_avg += 1
                continue

            recent_count = await session.scalar(
                select(func.count(VideoPublication.id))
                .join(VideoSubTask, VideoSubTask.id == VideoPublication.sub_task_id)
                .join(VideoTask, VideoTask.id == VideoSubTask.task_id)
                .where(VideoTask.account_id == account.id)
                .where(VideoPublication.status.in_(["completed", "partial"]))
                .where(VideoPublication.completed_at >= cutoff_recent)
            ) or 0
            if recent_count < _DEV_RECENT_VIDEO_MIN:
                skipped_low_recent += 1
                continue

            candidates.append((account, avg_views, recent_count))

        logger.info("=" * 72)
        logger.info("预计晋升 test→dev 的账号数: %d", len(candidates))
        logger.info(
            "跳过统计：发布数 < %d -> %d；均播 < %d -> %d；近 %d 天数 < %d -> %d",
            _DEV_LOOKBACK_VIDEOS, skipped_few_pubs,
            _DEV_AVG_VIEWS_MIN, skipped_low_avg,
            _DEV_LOOKBACK_DAYS, _DEV_RECENT_VIDEO_MIN, skipped_low_recent,
        )
        logger.info("-" * 72)
        for account, avg_views, recent_count in candidates:
            logger.info(
                "  %s | %s | avg_views=%.1f | last_%dd=%d",
                account.id, account.account_name, avg_views,
                _DEV_LOOKBACK_DAYS, recent_count,
            )
        logger.info("=" * 72)


async def _real_run(skip_dev_to_prod: bool) -> None:
    async with SessionLocal() as session:
        promoted_dev = await _evaluate_test_to_dev(session)
        promoted_prod = 0
        if not skip_dev_to_prod:
            promoted_prod = await _evaluate_dev_to_prod(session)
        else:
            logger.info("跳过 dev→prod 随机晋级（--skip-dev-to-prod）")

    logger.info("=" * 72)
    logger.info("完成 - test→dev: %d, dev→prod: %d", promoted_dev, promoted_prod)
    logger.info("=" * 72)


async def main() -> None:
    parser = argparse.ArgumentParser(description="手动触发账号分级评估")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只预览符合 test→dev 条件的账号，不修改 DB",
    )
    parser.add_argument(
        "--skip-dev-to-prod",
        action="store_true",
        help="跳过 dev→prod 随机晋级（适合冷启动阶段，仅做 test→dev）",
    )
    args = parser.parse_args()

    if args.dry_run:
        await _dry_run()
    else:
        await _real_run(skip_dev_to_prod=args.skip_dev_to_prod)


if __name__ == "__main__":
    asyncio.run(main())
