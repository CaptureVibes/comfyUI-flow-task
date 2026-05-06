"""
数据修正脚本：把库存内（status=queued 且标题已生成）的 publish_meta.title
改成新格式 — 去掉旧版后缀 "Get my exact look here 👀 👇"，并在前面拼接
"👇 👀 Get my exact look here 👀 👇 "。

筛选条件：
    video_sub_tasks.status = 'queued'
    AND publish_meta->>'status' = 'done'
    AND publish_meta->>'title' 非空
    AND publish_meta->>'promotion_code' 是 8 位数字（即「带了商品码」的视频）

    没有 promotion_code 的视频原本就没有任何后缀文案，不在改动范围内。

处理逻辑（幂等）：
    1. 若 title 已以新前缀开头 → 跳过
    2. 若 title 以旧后缀结尾 → 去掉旧后缀
    3. 在结果前拼接新前缀 + " "，并截到 100 字符（与运行时一致）
    4. 写回 publish_meta（仅改 title 字段）

⚠️ 不动 video_publications 已发布过的 title（用户要求只改库存）。

用法：
    cd backend
    uv run python scripts/rewrite_queued_publish_titles.py --dry-run
    uv run python scripts/rewrite_queued_publish_titles.py
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
from app.models.video_task import VideoSubTask
from app.services.publish_meta_service import (
    _PRODUCT_CODE_TITLE_LEGACY_SUFFIX as LEGACY_SUFFIX,
    _PRODUCT_CODE_TITLE_PREFIX as NEW_PREFIX,
    _build_product_code_title,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("rewrite_queued_publish_titles")

BATCH_COMMIT = 200


def rebuild_title(old: str) -> str:
    """复用运行时一样的逻辑，保证字段长度/边界一致。"""
    return _build_product_code_title(old)


def _has_promotion_code(meta: dict) -> bool:
    code = meta.get("promotion_code")
    return isinstance(code, str) and len(code) == 8 and code.isdigit()


async def cleanup(dry_run: bool = False) -> None:
    rewritten = 0
    skipped_already = 0
    skipped_no_title = 0
    skipped_no_code = 0
    total = 0

    async with SessionLocal() as db:
        stmt = (
            select(VideoSubTask)
            .where(VideoSubTask.status == "queued")
            .order_by(VideoSubTask.created_at)
        )
        sub_tasks: list[VideoSubTask] = list((await db.execute(stmt)).scalars().all())
        logger.info("共找到 %d 条 queued 子任务", len(sub_tasks))

        pending = 0
        for sub in sub_tasks:
            total += 1
            meta = sub.publish_meta if isinstance(sub.publish_meta, dict) else None
            if not meta or meta.get("status") != "done":
                skipped_no_title += 1
                continue
            old_title = meta.get("title")
            if not isinstance(old_title, str) or not old_title.strip():
                skipped_no_title += 1
                continue
            if not _has_promotion_code(meta):
                skipped_no_code += 1
                continue

            new_title = rebuild_title(old_title)
            if new_title == old_title:
                skipped_already += 1
                continue

            logger.info(
                "[%s] sub_task=%s code=%s\n    old: %r\n    new: %r",
                "DRY" if dry_run else "FIX",
                sub.id,
                meta.get("promotion_code"),
                old_title,
                new_title,
            )

            if not dry_run:
                # 浅拷贝后改 title，再整体赋值，确保 SQLAlchemy 检测到 JSON 字段变更
                sub.publish_meta = {**meta, "title": new_title}
                pending += 1

            rewritten += 1

            if not dry_run and pending >= BATCH_COMMIT:
                await db.commit()
                logger.info("已提交 %d 条", pending)
                pending = 0

        if not dry_run and pending:
            await db.commit()
            logger.info("已提交剩余 %d 条", pending)

    logger.info(
        "完成：扫描 %d 条；改写 %d 条；已是新格式跳过 %d 条；"
        "无标题/未完成生成跳过 %d 条；无商品码跳过 %d 条%s",
        total,
        rewritten,
        skipped_already,
        skipped_no_title,
        skipped_no_code,
        "（dry-run，未写入）" if dry_run else "",
    )


if __name__ == "__main__":
    logger.info("旧后缀: %r", LEGACY_SUFFIX)
    logger.info("新前缀: %r", NEW_PREFIX)
    parser = argparse.ArgumentParser(description="清洗 queued 子任务的 publish_meta.title")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写库")
    args = parser.parse_args()
    asyncio.run(cleanup(dry_run=args.dry_run))
