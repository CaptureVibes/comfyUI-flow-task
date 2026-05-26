"""
数据回填脚本：为 accounts.account_signature 开头统一补齐引流 prefix

背景：
    新版 name_handle_service 自动生成 AI 博主签名时，会在开头拼接
    「Outfits from my videos are available through the link below 💗」。
    本脚本把存量账号的签名也刷一遍。

    历史背景：之前误把这句话当 suffix 加到末尾并跑过一遍脚本，本次回填
    会同时把放错位置的末尾文案剥掉再前置（幂等、不会重复）。

处理逻辑（幂等）：
    - 已以 prefix 开头的账号跳过
    - 签名为空 / None 的账号跳过（避免给未完成生成的账号写无意义签名）
    - 其余账号：若文案错位于末尾，先剥掉再前置；否则直接前置

用法：
    cd backend
    uv run python scripts/backfill_account_signature_prefix.py [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.account import Account
from app.services.name_handle_service import _SIGNATURE_BIO_PREFIX, _ensure_signature_prefix

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_account_signature_prefix")


async def backfill(dry_run: bool = False) -> None:
    async with SessionLocal() as db:
        accounts = (await db.execute(select(Account))).scalars().all()

        total = len(accounts)
        updated_prepend = 0       # 仅前置（无脏数据）
        updated_relocated = 0     # 末尾脏数据 → 前置
        skipped_empty = 0
        skipped_already = 0

        logger.info("共扫描 %d 个账号", total)

        for account in accounts:
            sig_raw = account.account_signature or ""
            sig = sig_raw.strip()

            if not sig:
                skipped_empty += 1
                continue
            if sig.startswith(_SIGNATURE_BIO_PREFIX):
                skipped_already += 1
                continue

            was_misplaced = sig.endswith(_SIGNATURE_BIO_PREFIX)
            new_sig = _ensure_signature_prefix(sig)

            if was_misplaced:
                updated_relocated += 1
                logger.info(
                    "  account_id=%s name=%r → 末尾文案剥离 + 前置",
                    account.id, account.account_name,
                )
            else:
                updated_prepend += 1
                logger.info(
                    "  account_id=%s name=%r → 前置 prefix",
                    account.id, account.account_name,
                )

            if not dry_run:
                account.account_signature = new_sig

        summary = (
            f"前置 {updated_prepend} 条, 末尾→前置 {updated_relocated} 条, "
            f"空签名跳过 {skipped_empty} 条, 已含 prefix 跳过 {skipped_already} 条"
        )
        if dry_run:
            logger.info("[dry-run] %s", summary)
        else:
            await db.commit()
            logger.info("已更新, %s", summary)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只打印不写库")
    args = parser.parse_args()
    asyncio.run(backfill(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
