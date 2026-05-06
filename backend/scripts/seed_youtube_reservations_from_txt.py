"""
数据脚本：从 1.txt 读取一批 account_id，给「在 account_channel_reservations 里
没有对应 (account_id, platform=youtube) 记录」的账号补一条记录。

新增记录字段：
    platform        = "youtube"
    status          = "confirmed"
    source          = "openapi"
    channel_source  = "openapi"
    reserved_at / confirmed_at / created_at / updated_at = utcnow() （同一时间戳）

⚠️ 不会覆盖已有记录。表上有 uq_account_channel_reservations_account_platform
唯一约束，重复账号会被先 SELECT 过滤掉，理论上不会触发约束冲突。

可选校验：默认会校验 account_id 必须存在于 accounts 表（避免 FK 失败）。
找不到 account 的会被跳过并打印 warning。

输入文件格式：每行一个 UUID（允许空行 / 行首尾空白；# 开头视为注释）。

用法：
    cd backend
    uv run python scripts/seed_youtube_reservations_from_txt.py --dry-run
    uv run python scripts/seed_youtube_reservations_from_txt.py
    uv run python scripts/seed_youtube_reservations_from_txt.py --input scripts/1.txt
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.account import Account
from app.models.account_channel_reservation import AccountChannelReservation

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("seed_youtube_reservations")

PLATFORM = "youtube"
STATUS = "confirmed"
CHANNEL_SOURCE = "openapi"
SOURCE = "openapi"
BATCH_COMMIT = 200


def _read_account_ids(path: str) -> list[uuid.UUID]:
    ids: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    with open(path, "r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            try:
                aid = uuid.UUID(line)
            except ValueError:
                logger.warning("第 %d 行不是合法 UUID，已跳过：%r", lineno, line)
                continue
            if aid in seen:
                continue
            seen.add(aid)
            ids.append(aid)
    return ids


async def seed(input_path: str, dry_run: bool = False) -> None:
    account_ids = _read_account_ids(input_path)
    logger.info("从 %s 读到 %d 个唯一 account_id", input_path, len(account_ids))
    if not account_ids:
        return

    inserted = 0
    skipped_existing = 0
    skipped_no_account = 0
    now = datetime.now(timezone.utc)

    async with SessionLocal() as db:
        # 1. 先批量查 accounts 表，过滤不存在的 account_id
        existing_accounts = (
            await db.execute(
                select(Account.id).where(Account.id.in_(account_ids))
            )
        ).scalars().all()
        valid_account_ids = set(existing_accounts)
        invalid_ids = [aid for aid in account_ids if aid not in valid_account_ids]
        if invalid_ids:
            logger.warning(
                "%d 个 account_id 在 accounts 表中不存在，将跳过：%s%s",
                len(invalid_ids),
                ", ".join(str(x) for x in invalid_ids[:10]),
                "..." if len(invalid_ids) > 10 else "",
            )
            skipped_no_account = len(invalid_ids)

        target_ids = [aid for aid in account_ids if aid in valid_account_ids]

        # 2. 批量查已有 (account_id, platform=youtube) 的记录
        if target_ids:
            already = (
                await db.execute(
                    select(AccountChannelReservation.account_id)
                    .where(AccountChannelReservation.account_id.in_(target_ids))
                    .where(AccountChannelReservation.platform == PLATFORM)
                )
            ).scalars().all()
            already_set = set(already)
        else:
            already_set = set()

        skipped_existing = len(already_set)
        to_insert = [aid for aid in target_ids if aid not in already_set]

        logger.info(
            "校验结果：合法账号 %d / 已有 youtube 记录跳过 %d / 待插入 %d",
            len(target_ids),
            skipped_existing,
            len(to_insert),
        )

        # 3. 批量插入
        pending = 0
        for aid in to_insert:
            row = AccountChannelReservation(
                account_id=aid,
                platform=PLATFORM,
                status=STATUS,
                source=SOURCE,
                channel_source=CHANNEL_SOURCE,
                reserved_at=now,
                confirmed_at=now,
                created_at=now,
                updated_at=now,
            )
            logger.info(
                "[%s] insert account_id=%s platform=%s status=%s channel_source=%s",
                "DRY" if dry_run else "INS",
                aid,
                PLATFORM,
                STATUS,
                CHANNEL_SOURCE,
            )
            if not dry_run:
                db.add(row)
                pending += 1
                inserted += 1
                if pending >= BATCH_COMMIT:
                    await db.commit()
                    logger.info("已提交 %d 条", pending)
                    pending = 0
            else:
                inserted += 1

        if not dry_run and pending:
            await db.commit()
            logger.info("已提交剩余 %d 条", pending)

    logger.info(
        "完成：输入 %d；已存在跳过 %d；账号不存在跳过 %d；插入 %d%s",
        len(account_ids),
        skipped_existing,
        skipped_no_account,
        inserted,
        "（dry-run，未写入）" if dry_run else "",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="按 1.txt 给缺失 youtube reservation 的账号补建")
    parser.add_argument(
        "--input",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "1.txt"),
        help="UUID 列表文件路径，默认 backend/scripts/1.txt",
    )
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写库")
    args = parser.parse_args()
    asyncio.run(seed(input_path=args.input, dry_run=args.dry_run))
