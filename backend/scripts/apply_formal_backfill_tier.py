"""
按 formal-backfill 导出的 open_api_task_id 列表把对应 Account 标为「正式号」（prod），
其余账号统一标为「实验号」（test）。

输入：文本文件，每行一个 open_api_task_id（formal-backfill 页面「导出 task_ids」生成）。

处理：
    1. 读全部 task_id，去重。
    2. 链路反查：VideoPublication.open_api_task_id → sub_task → task → account_id
       得到一组「正式号」account_id。
    3. 对范围内所有 Account：account_id 命中 → tier='prod'；否则 → tier='test'。
       --owner-id 限定影响范围（推荐）；不传则覆盖所有 owner 的账号。

幂等：每次都按当前文件重新设置全量；可安全多次执行。

用法：
    cd backend
    uv run python scripts/apply_formal_backfill_tier.py [--dry-run]

默认参数（直接写死，不再要求传入）：
    file     = ../docs/formal_backfill_task_ids_2026-05-12.txt
    owner_id = 08851f2b-e155-4300-9686-656471961d45
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, update

from app.db.session import SessionLocal
from app.models.account import Account
from app.models.video_publication import VideoPublication
from app.models.video_task import VideoSubTask, VideoTask

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("apply_formal_backfill_tier")

# ── 固定参数 ───────────────────────────────────────────────────────────────
_DEFAULT_FILE = Path(__file__).resolve().parent.parent.parent / "docs" / "formal_backfill_task_ids_2026-05-12.txt"
_DEFAULT_OWNER_ID = uuid.UUID("08851f2b-e155-4300-9686-656471961d45")


def read_task_ids(path: Path) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            t = line.strip()
            if not t or t in seen:
                continue
            seen.add(t)
            ids.append(t)
    return ids


async def resolve_prod_account_ids(
    task_ids: list[str], owner_id: uuid.UUID | None
) -> tuple[set[uuid.UUID], list[str]]:
    """task_id → account_id；返回 (命中的 account_id 集合, 未命中的 task_id 列表)。"""
    async with SessionLocal() as db:
        stmt = (
            select(VideoPublication.open_api_task_id, VideoTask.account_id)
            .join(VideoSubTask, VideoSubTask.id == VideoPublication.sub_task_id)
            .join(VideoTask, VideoTask.id == VideoSubTask.task_id)
            .where(VideoPublication.open_api_task_id.in_(task_ids))
        )
        if owner_id is not None:
            stmt = stmt.where(VideoTask.owner_id == owner_id)
        rows = (await db.execute(stmt)).all()

    found_tasks: set[str] = set()
    account_ids: set[uuid.UUID] = set()
    for tid, aid in rows:
        if tid is None or aid is None:
            continue
        found_tasks.add(tid)
        account_ids.add(aid)

    missing = [t for t in task_ids if t not in found_tasks]
    return account_ids, missing


async def apply_tiers(
    prod_account_ids: set[uuid.UUID],
    owner_id: uuid.UUID | None,
    dry_run: bool,
) -> dict:
    """把 prod_account_ids 内的账号置 tier='prod'，范围内其他置 tier='test'。"""
    async with SessionLocal() as db:
        scope = select(Account)
        if owner_id is not None:
            scope = scope.where(Account.owner_id == owner_id)
        accounts = (await db.execute(scope)).scalars().all()

        to_prod_changed = 0
        to_test_changed = 0
        already_prod = 0
        already_test = 0
        for a in accounts:
            target = "prod" if a.id in prod_account_ids else "test"
            if a.account_tier == target:
                if target == "prod":
                    already_prod += 1
                else:
                    already_test += 1
                continue
            if not dry_run:
                a.account_tier = target
            if target == "prod":
                to_prod_changed += 1
            else:
                to_test_changed += 1

        if not dry_run:
            await db.commit()

    return {
        "total_accounts_in_scope": len(accounts),
        "set_prod": to_prod_changed,
        "set_test": to_test_changed,
        "already_prod": already_prod,
        "already_test": already_test,
    }


async def main_async(args: argparse.Namespace) -> None:
    path = _DEFAULT_FILE
    if not path.exists():
        logger.error("文件不存在: %s", path)
        sys.exit(1)

    task_ids = read_task_ids(path)
    logger.info("读取 %s: %d 条 task_id（去重后）", path, len(task_ids))
    if not task_ids:
        logger.warning("文件为空，退出。")
        return

    owner_id = _DEFAULT_OWNER_ID
    logger.info("owner_id = %s", owner_id)

    prod_account_ids, missing = await resolve_prod_account_ids(task_ids, owner_id)
    logger.info("反查到 prod 候选账号: %d 个", len(prod_account_ids))
    if missing:
        logger.warning("以下 %d 条 task_id 未匹配到 publication（前 10 条）:", len(missing))
        for t in missing[:10]:
            logger.warning("  %s", t)

    summary = await apply_tiers(prod_account_ids, owner_id, args.dry_run)
    logger.info(
        "处理完成（%s）：scope=%d, set_prod=%d, set_test=%d, already_prod=%d, already_test=%d",
        "DRY RUN" if args.dry_run else "已写库",
        summary["total_accounts_in_scope"],
        summary["set_prod"],
        summary["set_test"],
        summary["already_prod"],
        summary["already_test"],
    )


def main() -> None:
    p = argparse.ArgumentParser(description="按 formal-backfill 导出的 task_id 列表设置账号 tier")
    p.add_argument("--dry-run", action="store_true", help="只统计不写库")
    args = p.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
