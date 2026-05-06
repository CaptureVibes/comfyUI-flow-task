"""
数据修正脚本：清理「无商品码」账号下历史 video_publications 误分配的 promotion_code

背景：
    create_publication 之前在 publish_meta.promotion_code 为空时会无脑兜底分配
    promotion_code，导致 product_code_mode != "with_code" 的账号也被打上 code。
    本脚本回收这些误分配的 code（数据库 + request_payload），并把内存里的
    promotion_code_distributor 状态同步释放回池中。

处理逻辑（幂等）：
    1. 联表 video_publications → video_sub_tasks → video_tasks → accounts
    2. 命中条件：promotion_code IS NOT NULL 且账号 product_code_mode != 'with_code'
       （包含 product_code_mode IS NULL / 'without_code' / 找不到 account 的情况）
    3. 将 video_publications.promotion_code 置 NULL；
       request_payload.promotion_code 同步置 None（保留键，兼容历史读取）
    4. 同步清理同一 sub_task 的 publish_meta.promotion_code / product_code_mode
       （这些是 publish_meta_service 用于重新生成的字段，留着会再次传染）
    5. dry-run 模式只打印不写

用法：
    cd backend
    uv run python scripts/cleanup_promotion_code_for_without_code.py --dry-run
    uv run python scripts/cleanup_promotion_code_for_without_code.py
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
from app.models.video_publication import VideoPublication
from app.models.video_task import VideoSubTask, VideoTask

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("cleanup_promotion_code")

BATCH_COMMIT = 200


def _strip_meta(meta: dict | None) -> tuple[dict | None, bool]:
    """从 publish_meta 中移除 promotion_code / product_code_mode / ext_products_count。

    返回 (新 dict 或 None, 是否被改动)。
    """
    if not isinstance(meta, dict):
        return meta, False
    keys = ("promotion_code", "product_code_mode", "ext_products_count")
    if not any(k in meta for k in keys):
        return meta, False
    new_meta = {k: v for k, v in meta.items() if k not in keys}
    return (new_meta or None), True


async def cleanup(dry_run: bool = False) -> None:
    cleared_pub = 0
    cleared_meta = 0
    skipped = 0
    seen_codes: set[str] = set()  # 用于去重日志统计

    async with SessionLocal() as db:
        # 一次性把候选记录 + 关联账号信息拉出来
        stmt = (
            select(VideoPublication, VideoSubTask, VideoTask, Account)
            .join(VideoSubTask, VideoSubTask.id == VideoPublication.sub_task_id)
            .join(VideoTask, VideoTask.id == VideoSubTask.task_id)
            .outerjoin(Account, Account.id == VideoTask.account_id)
            .where(VideoPublication.promotion_code.is_not(None))
            .order_by(VideoPublication.created_at)
        )
        rows = (await db.execute(stmt)).all()
        logger.info("共找到 %d 条带 promotion_code 的 publication 候选", len(rows))

        pending_in_batch = 0
        for pub, sub_task, _task, account in rows:
            mode = (account.product_code_mode if account is not None else None) or None
            if mode == "with_code":
                skipped += 1
                continue

            old_code = pub.promotion_code
            seen_codes.add(old_code)
            payload = pub.request_payload if isinstance(pub.request_payload, dict) else {}
            new_payload = (
                {**payload, "promotion_code": None}
                if "promotion_code" in payload or payload
                else payload
            )
            new_meta, meta_changed = _strip_meta(sub_task.publish_meta)

            logger.info(
                "[%s] pub=%s sub_task=%s account=%s mode=%s code=%s%s",
                "DRY" if dry_run else "FIX",
                pub.id,
                pub.sub_task_id,
                account.id if account else None,
                mode,
                old_code,
                " (+meta)" if meta_changed else "",
            )

            if not dry_run:
                pub.promotion_code = None
                if isinstance(payload, dict):
                    pub.request_payload = new_payload
                if meta_changed:
                    sub_task.publish_meta = new_meta
                pending_in_batch += 1

            cleared_pub += 1
            if meta_changed:
                cleared_meta += 1

            if not dry_run and pending_in_batch >= BATCH_COMMIT:
                await db.commit()
                logger.info("已提交 %d 条", pending_in_batch)
                pending_in_batch = 0

        if not dry_run and pending_in_batch:
            await db.commit()
            logger.info("已提交剩余 %d 条", pending_in_batch)

    logger.info(
        "完成：清理 publication %d 条（涉及 %d 个不同 code），同步清理 publish_meta %d 条，跳过（with_code）%d 条%s",
        cleared_pub,
        len(seen_codes),
        cleared_meta,
        skipped,
        "（dry-run，未写入）" if dry_run else "",
    )
    if not dry_run and seen_codes:
        logger.info(
            "提示：被清理的 code 仍记录在 promotion_codes 表里（已使用过）；"
            "如需把它们退回可用池，请单独评估后再处理。"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="清理无商品码账号下误分配的 promotion_code")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写库")
    args = parser.parse_args()
    asyncio.run(cleanup(dry_run=args.dry_run))
