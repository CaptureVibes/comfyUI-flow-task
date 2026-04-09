"""
数据回填脚本：通过 account_tags → video_source_tags → video_sources 推导
account_id <-> tiktok_blogger_id 绑定关系，写入 account_tiktok_bloggers。

关联链路：
  account_tags (account_id, tag_id)
    → video_source_tags (tag_id → video_source_id)
    → video_sources (tiktok_blogger_id)
    → account_tiktok_bloggers (account_id, tiktok_blogger_id)

逻辑：
- 对每条 account_tag 记录，通过 tag_id 在 video_source_tags 中找到关联的
  video_source_id（有多个时取第一个有 tiktok_blogger_id 的）
- 若找到 tiktok_blogger_id，则在 account_tiktok_bloggers 中 upsert（已存在跳过）

用法：
    cd backend
    uv run python scripts/backfill_account_blogger_bindings.py
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, text

from app.db.session import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_account_blogger_bindings")


async def main() -> None:
    logger.info("Starting account_tiktok_bloggers backfill...")

    async with SessionLocal() as session:
        # 一次性拉取所有 account_tags
        rows = (await session.execute(
            text("SELECT id, account_id, tag_id FROM account_tags ORDER BY created_at ASC")
        )).fetchall()

    logger.info("Found %d account_tag records", len(rows))

    inserted = 0
    skipped_no_video = 0
    skipped_no_blogger = 0
    skipped_exists = 0
    errors = 0

    for row in rows:
        at_id, account_id, tag_id = row

        try:
            async with SessionLocal() as session:
                # 通过 tag_id 找关联的 video_source（取第一个有 tiktok_blogger_id 的）
                vs_rows = (await session.execute(
                    text("""
                        SELECT vs.tiktok_blogger_id
                        FROM video_source_tags vst
                        JOIN video_sources vs ON vs.id = vst.video_source_id
                        WHERE vst.tag_id = :tag_id
                          AND vst.video_source_id IS NOT NULL
                          AND vs.tiktok_blogger_id IS NOT NULL
                        LIMIT 1
                    """),
                    {"tag_id": tag_id},
                )).fetchall()

                if not vs_rows:
                    # 尝试看看 tag 有没有关联任何 video_source（不含 blogger）
                    any_vs = (await session.execute(
                        text("""
                            SELECT 1 FROM video_source_tags
                            WHERE tag_id = :tag_id AND video_source_id IS NOT NULL
                            LIMIT 1
                        """),
                        {"tag_id": tag_id},
                    )).fetchone()
                    if any_vs:
                        skipped_no_blogger += 1
                        logger.debug(
                            "account_tag id=%s: tag has video_sources but none have tiktok_blogger_id", at_id
                        )
                    else:
                        skipped_no_video += 1
                        logger.debug("account_tag id=%s: tag has no associated video_source", at_id)
                    continue

                tiktok_blogger_id = vs_rows[0][0]

                # 检查是否已存在
                existing = (await session.execute(
                    text("""
                        SELECT 1 FROM account_tiktok_bloggers
                        WHERE account_id = :account_id AND tiktok_blogger_id = :blogger_id
                    """),
                    {"account_id": account_id, "blogger_id": tiktok_blogger_id},
                )).fetchone()

                if existing:
                    skipped_exists += 1
                    logger.debug(
                        "account_tag id=%s: binding already exists (account=%s, blogger=%s)",
                        at_id, account_id, tiktok_blogger_id,
                    )
                    continue

                # 插入新绑定
                new_id = uuid.uuid4()
                now = datetime.now(timezone.utc)
                await session.execute(
                    text("""
                        INSERT INTO account_tiktok_bloggers (id, account_id, tiktok_blogger_id, created_at)
                        VALUES (:id, :account_id, :blogger_id, :created_at)
                    """),
                    {
                        "id": new_id,
                        "account_id": account_id,
                        "blogger_id": tiktok_blogger_id,
                        "created_at": now,
                    },
                )
                await session.commit()
                inserted += 1
                logger.info(
                    "Inserted: account=%s <-> blogger=%s (via tag=%s)",
                    account_id, tiktok_blogger_id, tag_id,
                )

        except Exception as exc:
            errors += 1
            logger.warning("Error processing account_tag id=%s: %s", at_id, exc)

    logger.info(
        "Backfill complete: inserted=%d skipped_exists=%d "
        "skipped_no_blogger=%d skipped_no_video=%d errors=%d",
        inserted, skipped_exists, skipped_no_blogger, skipped_no_video, errors,
    )


if __name__ == "__main__":
    asyncio.run(main())
