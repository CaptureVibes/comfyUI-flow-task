"""
数据回填脚本：为历史 video_publications 记录补充 _source / _has_openapi / _has_ext_pub 字段

背景：
    引入外部发布 API（ext_pub）适配器后，channels_status 里每条需要有 _source 字段，
    request_payload 里需要有 _has_openapi / _has_ext_pub 标记，供 sync_publication_status
    判断调用哪侧适配器。历史数据没有这些字段，回填后轮询器才能正确工作。

处理逻辑（幂等）：
    1. 跳过 request_payload 已有 _has_openapi 的记录（已是新数据）
    2. channels_status 里每条若无 _source，补 "_source": "openapi"（历史数据全是内部频道）
    3. request_payload 补 "_has_openapi": True, "_has_ext_pub": False
       - 若 open_api_task_id 为空且无 channels_status，则两者均为 False（避免误轮询）

用法：
    cd backend
    uv run python scripts/backfill_publication_sources.py [--dry-run]
"""
from __future__ import annotations

import asyncio
import logging
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.video_publication import VideoPublication

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_publication_sources")

BATCH_SIZE = 100
_SOURCE_OPENAPI = "openapi"


async def backfill(dry_run: bool = False) -> None:
    updated = 0
    skipped = 0
    total = 0

    async with SessionLocal() as db:
        result = await db.execute(select(VideoPublication).order_by(VideoPublication.created_at))
        publications: list[VideoPublication] = list(result.scalars().all())

    logger.info("共找到 %d 条 video_publications 记录", len(publications))

    batch: list[VideoPublication] = []

    for pub in publications:
        total += 1
        payload: dict = pub.request_payload or {}

        # 已回填过，跳过
        if "_has_openapi" in payload:
            skipped += 1
            continue

        # ── 处理 channels_status ──────────────────────────────────────────────
        channels_status: list[dict] = pub.channels_status or []
        new_channels_status = []
        for ch in channels_status:
            if not isinstance(ch, dict):
                new_channels_status.append(ch)
                continue
            if "_source" not in ch:
                ch = {**ch, "_source": _SOURCE_OPENAPI}
            new_channels_status.append(ch)

        # ── 判断 has_openapi ──────────────────────────────────────────────────
        # 历史数据全是内部频道，但若 open_api_task_id 为空且无 channels，保守置 False
        has_openapi = bool(pub.open_api_task_id or new_channels_status)
        has_ext_pub = False

        new_payload = {
            **payload,
            "_has_openapi": has_openapi,
            "_has_ext_pub": has_ext_pub,
        }

        logger.info(
            "[%s] pub=%s status=%s open_api_task_id=%s channels=%d → has_openapi=%s has_ext_pub=%s",
            "DRY" if dry_run else "UPD",
            pub.id, pub.status, pub.open_api_task_id,
            len(new_channels_status), has_openapi, has_ext_pub,
        )

        if not dry_run:
            pub.request_payload = new_payload
            pub.channels_status = new_channels_status or None
            batch.append(pub)

        updated += 1

        if not dry_run and len(batch) >= BATCH_SIZE:
            async with SessionLocal() as db:
                for p in batch:
                    await db.merge(p)
                await db.commit()
            logger.info("已提交 %d 条", len(batch))
            batch.clear()

    # 提交剩余
    if not dry_run and batch:
        async with SessionLocal() as db:
            for p in batch:
                await db.merge(p)
            await db.commit()
        logger.info("已提交剩余 %d 条", len(batch))

    logger.info(
        "完成：总计 %d 条，更新 %d 条，跳过（已回填）%d 条%s",
        total, updated, skipped, "（dry-run，未写入）" if dry_run else "",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="回填 video_publications _source/_has_* 字段")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写入数据库")
    args = parser.parse_args()
    asyncio.run(backfill(dry_run=args.dry_run))
