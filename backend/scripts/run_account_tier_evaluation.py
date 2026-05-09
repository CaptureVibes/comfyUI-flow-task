"""
手动触发账号分级评估（冷启动 / 临时补跑用）

用法：
    cd backend

    # 预览所有 owner 的 test↔dev 变动列表，不修改 DB
    uv run python scripts/run_account_tier_evaluation.py --dry-run

    # 仅执行 test↔dev 双向调整（跳过 dev→prod 随机扩量），适合冷启动阶段
    uv run python scripts/run_account_tier_evaluation.py --skip-dev-to-prod

    # 执行完整两步（等同于每日定时任务）
    uv run python scripts/run_account_tier_evaluation.py

判定规则与阈值现在从每个 owner 的 pipeline_settings 读取：
- 实验号 (test) ↔ 常规号 (dev)：满足条件升 dev，不满足降 test。
- 常规号 (dev) → 正式号 (prod)：random.uniform(min_rate, max_rate) * 当前 prod 数。
- 正式号 (prod) 永不被自动改动。
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models.account import Account  # noqa: E402
from app.services.account_tier_scheduler import (  # noqa: E402
    apply_tier_changes,
    compute_tier_changes,
    evaluate_dev_to_prod,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scripts.run_account_tier_evaluation")


async def _list_owner_ids() -> list:
    async with SessionLocal() as session:
        rows = (await session.execute(select(Account.owner_id).distinct())).all()
    return [row[0] for row in rows]


async def _dry_run() -> None:
    owner_ids = await _list_owner_ids()
    logger.info("待扫描 owner 数: %d", len(owner_ids))

    grand_promote = 0
    grand_demote = 0
    for owner_id in owner_ids:
        async with SessionLocal() as session:
            changes = await compute_tier_changes(session, owner_id)
        if not changes:
            logger.info("owner=%s 无变动", owner_id)
            continue
        promote = sum(1 for c in changes if c["target_tier"] == "dev")
        demote = sum(1 for c in changes if c["target_tier"] == "test")
        grand_promote += promote
        grand_demote += demote
        logger.info("owner=%s 预计 test→dev=%d, dev→test=%d", owner_id, promote, demote)
        for c in changes:
            arrow = "→" if c["target_tier"] == "dev" else "←"
            r = c.get("reason", {})
            logger.info(
                "  %s %s %s | %s | sample=%s avg_views=%s recent=%s",
                c["account_id"],
                f"{c['current_tier']}{arrow}{c['target_tier']}",
                (c["account_name"] or "")[:40],
                "✓" if c["target_tier"] == "dev" else "✗",
                r.get("video_count_in_sample"),
                r.get("avg_views"),
                r.get("recent_count"),
            )
    logger.info("=" * 72)
    logger.info("汇总（不落库）- test→dev: %d, dev→test: %d", grand_promote, grand_demote)
    logger.info("=" * 72)


async def _real_run(skip_dev_to_prod: bool) -> None:
    owner_ids = await _list_owner_ids()
    logger.info("待评估 owner 数: %d", len(owner_ids))

    total_promote = 0
    total_demote = 0
    total_prod = 0
    for owner_id in owner_ids:
        async with SessionLocal() as session:
            changes = await compute_tier_changes(session, owner_id)
            res = await apply_tier_changes(session, owner_id, changes)
            promoted_prod = 0
            if not skip_dev_to_prod:
                promoted_prod = await evaluate_dev_to_prod(session, owner_id)
        total_promote += res.get("promoted", 0)
        total_demote += res.get("demoted", 0)
        total_prod += promoted_prod

    if skip_dev_to_prod:
        logger.info("跳过 dev→prod 随机扩量（--skip-dev-to-prod）")
    logger.info("=" * 72)
    logger.info(
        "完成 - test→dev: %d, dev→test: %d, dev→prod: %d",
        total_promote, total_demote, total_prod,
    )
    logger.info("=" * 72)


async def main() -> None:
    parser = argparse.ArgumentParser(description="手动触发账号分级评估")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不修改 DB")
    parser.add_argument(
        "--skip-dev-to-prod",
        action="store_true",
        help="跳过 dev→prod 随机扩量（适合冷启动阶段，仅做 test↔dev）",
    )
    args = parser.parse_args()

    if args.dry_run:
        await _dry_run()
    else:
        await _real_run(skip_dev_to_prod=args.skip_dev_to_prod)


if __name__ == "__main__":
    asyncio.run(main())
