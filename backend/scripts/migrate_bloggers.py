"""
数据迁移脚本：为现有 video_sources 记录创建/关联 tiktok_bloggers，并补充头像

用法（在 alembic upgrade head 之后运行）：
    cd backend
    uv run python scripts/migrate_bloggers.py

特性：
- 幂等：跳过已有 tiktok_blogger_id 的记录
- 出错时单条回滚，继续处理剩余记录
- 每 50 条批量 commit
- 自动为 avatar_url 为空的博主获取头像（通过 yt-dlp 解析 TikTok 用户页面）
"""
from __future__ import annotations

import asyncio
import logging
import sys
import os

# Make sure app modules are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.tiktok_blogger import TiktokBlogger
from app.models.video_source import VideoSource
from app.services.tiktok_blogger_service import (
    upsert_blogger_from_info,
    _extract_tiktok_user_info_from_webpage,
    _download_and_upload_avatar,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("migrate_bloggers")

BATCH_SIZE = 50


async def _fetch_avatar_for_blogger(blogger: TiktokBlogger) -> str | None:
    """Use yt-dlp to fetch TikTok avatar for a blogger that has no avatar_url yet."""
    if blogger.platform != "tiktok":
        return None
    handle = blogger.blogger_handle or (
        blogger.blogger_url.split("@")[-1].split("/")[0] if blogger.blogger_url and "@" in blogger.blogger_url else None
    )
    if not handle:
        return None

    profile_url = f"https://www.tiktok.com/@{handle}"

    def _run() -> str | None:
        try:
            import yt_dlp  # type: ignore
        except ImportError:
            return None
        ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            _, raw_avatar = _extract_tiktok_user_info_from_webpage(ydl, profile_url)
            return raw_avatar

    try:
        raw_avatar = await asyncio.to_thread(_run)
    except Exception as exc:
        logger.debug("Avatar fetch failed for @%s: %s", handle, exc)
        return None

    if raw_avatar:
        cdn_url = await _download_and_upload_avatar(raw_avatar)
        return cdn_url
    return None


async def main() -> None:
    logger.info("Starting blogger migration...")

    # Step 1: Link video_sources to tiktok_bloggers
    async with SessionLocal() as session:
        stmt = (
            select(VideoSource)
            .where(VideoSource.tiktok_blogger_id.is_(None))
            .where(VideoSource.extra.is_not(None))
            .order_by(VideoSource.created_at.asc())
        )
        rows: list[VideoSource] = list((await session.scalars(stmt)).all())

    logger.info("Found %d video_sources to process", len(rows))

    processed = 0
    linked = 0
    skipped = 0
    errors = 0

    for i, vs in enumerate(rows):
        try:
            async with SessionLocal() as session:
                # Re-fetch within new session
                vs_obj = await session.get(VideoSource, vs.id)
                if vs_obj is None or vs_obj.tiktok_blogger_id is not None:
                    skipped += 1
                    continue

                info = vs_obj.extra or {}
                blogger = await upsert_blogger_from_info(session, info, vs_obj.owner_id)
                if blogger is not None:
                    await session.flush()
                    vs_obj.tiktok_blogger_id = blogger.id
                    linked += 1
                else:
                    skipped += 1

                await session.commit()
                processed += 1

                if processed % BATCH_SIZE == 0:
                    logger.info(
                        "Progress: processed=%d linked=%d skipped=%d errors=%d",
                        processed, linked, skipped, errors,
                    )

        except Exception as exc:
            errors += 1
            logger.warning("Error processing video_source id=%s: %s", vs.id, exc)

    logger.info(
        "Video link migration complete: processed=%d linked=%d skipped=%d errors=%d",
        processed, linked, skipped, errors,
    )

    # Step 2: Fetch avatars for bloggers with no avatar_url
    logger.info("Fetching avatars for bloggers with no avatar...")
    async with SessionLocal() as session:
        blogger_rows = list((await session.scalars(
            select(TiktokBlogger).where(TiktokBlogger.avatar_url.is_(None))
        )).all())

    logger.info("Found %d bloggers without avatar", len(blogger_rows))

    avatar_updated = 0
    avatar_failed = 0

    for blogger in blogger_rows:
        try:
            cdn_url = await _fetch_avatar_for_blogger(blogger)
            if cdn_url:
                async with SessionLocal() as session:
                    b = await session.get(TiktokBlogger, blogger.id)
                    if b and not b.avatar_url:
                        b.avatar_url = cdn_url
                        await session.commit()
                        avatar_updated += 1
                        logger.info("Avatar set for blogger @%s: %s", b.blogger_handle, cdn_url[:80])
            else:
                avatar_failed += 1
                logger.debug("No avatar found for blogger @%s", blogger.blogger_handle)
        except Exception as exc:
            avatar_failed += 1
            logger.warning("Avatar fetch error for blogger id=%s: %s", blogger.id, exc)

    logger.info(
        "Avatar migration complete: updated=%d failed=%d",
        avatar_updated, avatar_failed,
    )


if __name__ == "__main__":
    asyncio.run(main())
