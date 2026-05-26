"""
数据回填脚本：为 accounts.account_signature 末尾统一补齐引流 suffix

背景：
    新版 name_handle_service 自动生成 AI 博主签名时，会在末尾拼接
    「Outfits from my videos are available through the link below 💗」。
    本脚本把存量账号的签名也刷一遍。

处理逻辑（幂等）：
    - 已包含 suffix 的账号跳过
    - 签名为空 / None 的账号跳过（避免给未完成生成的账号写无意义签名）
    - 其余账号末尾追加 "\n\n{suffix}"

用法：
    cd backend
    uv run python scripts/backfill_account_signature_suffix.py [--dry-run]
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
from app.services.name_handle_service import _SIGNATURE_BIO_SUFFIX

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_account_signature_suffix")


async def backfill(dry_run: bool = False) -> None:
    async with SessionLocal() as db:
        accounts = (await db.execute(select(Account))).scalars().all()

        total = len(accounts)
        updated = 0
        skipped_empty = 0
        skipped_already = 0

        logger.info("共扫描 %d 个账号", total)

        for account in accounts:
            sig = (account.account_signature or "").rstrip()
            if not sig:
                skipped_empty += 1
                continue
            if _SIGNATURE_BIO_SUFFIX in sig:
                skipped_already += 1
                continue

            new_sig = f"{sig}\n\n{_SIGNATURE_BIO_SUFFIX}"
            logger.info(
                "  account_id=%s name=%r → 追加 suffix",
                account.id, account.account_name,
            )
            if not dry_run:
                account.account_signature = new_sig
            updated += 1

        if dry_run:
            logger.info("[dry-run] 预计更新 %d 条，跳过 %d 条空签名，%d 条已含 suffix",
                        updated, skipped_empty, skipped_already)
        else:
            await db.commit()
            logger.info("已更新 %d 条，跳过 %d 条空签名，%d 条已含 suffix",
                        updated, skipped_empty, skipped_already)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只打印不写库")
    args = parser.parse_args()
    asyncio.run(backfill(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
