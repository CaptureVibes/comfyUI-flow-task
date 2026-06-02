"""把现有 video_sources.local_video_url（旧 CDN 链接）里的视频搬到 GCS。

用法（在 alembic upgrade head 之后运行）：
    cd backend
    uv run python scripts/migrate_local_video_url_to_gcs.py            # 处理所有未搬迁的
    uv run python scripts/migrate_local_video_url_to_gcs.py --limit 50 # 只处理前 50 条
    uv run python scripts/migrate_local_video_url_to_gcs.py --concurrency 4

特性：
- 幂等：跳过已经有 local_gcs_video_url 的记录
- 单条失败不影响其它（日志记录失败原因）
- 每条独立 commit，安全可中断重跑
- 不清空 local_video_url（旧 CDN 链接保留作为前端回退播放源）
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from typing import Iterable

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.video_source import VideoSource
from app.utils.gcs_download import download_url_to_local
from app.utils.gcs_utils import upload_video_file_to_gcs
from app.utils.tmp_storage import disk_namedtempfile, ensure_free_space

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("migrate_local_video_url_to_gcs")


def _today_gcs_prefix() -> str:
    from datetime import datetime, timezone

    from app.core.config import settings

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    base = (settings.gcs_video_prefix or "video-sources").strip("/")
    return f"{base}/{date_str}"


async def _migrate_one(vs_id) -> tuple[str, str | None]:
    """处理单条记录。返回 (status, error)。status ∈ {migrated, skipped, failed}。"""
    async with SessionLocal() as session:
        vs = await session.get(VideoSource, vs_id)
        if vs is None:
            return ("skipped", "row 不存在")
        if vs.local_gcs_video_url:
            return ("skipped", "已有 local_gcs_video_url")
        source_url = vs.local_video_url
        if not source_url:
            return ("skipped", "无 local_video_url")

    try:
        ensure_free_space(min_bytes=500 * 1024 * 1024, label="migrate_to_gcs")
    except Exception as exc:
        return ("failed", f"磁盘空间不足: {exc}")

    with disk_namedtempfile(suffix=".mp4", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        try:
            size = await download_url_to_local(source_url, tmp_path, timeout=600.0)
        except Exception as exc:
            return ("failed", f"下载失败: {exc}")
        if size == 0:
            return ("failed", "下载得到 0 字节")
        try:
            result = await upload_video_file_to_gcs(
                tmp_path,
                object_prefix=_today_gcs_prefix(),
                content_type="video/mp4",
            )
        except Exception as exc:
            return ("failed", f"上传 GCS 失败: {exc}")

        async with SessionLocal() as session:
            vs = await session.get(VideoSource, vs_id)
            if vs is None:
                return ("skipped", "row 已被删除")
            vs.local_gcs_video_url = result.public_url
            await session.commit()
        logger.info(
            "[migrate] %s ok: cdn=%s gcs=%s size=%.1fMB",
            vs_id, source_url[:80], result.public_url[:120], size / 1024 / 1024,
        )
        return ("migrated", None)
    finally:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass


async def _list_candidates(limit: int | None) -> list:
    async with SessionLocal() as session:
        stmt = (
            select(VideoSource.id)
            .where(VideoSource.local_video_url.is_not(None))
            .where(VideoSource.local_video_url != "")
            .where(VideoSource.local_gcs_video_url.is_(None))
            .order_by(VideoSource.created_at.asc())
        )
        if limit:
            stmt = stmt.limit(limit)
        return list((await session.execute(stmt)).scalars().all())


async def _run(concurrency: int, limit: int | None) -> None:
    ids = await _list_candidates(limit)
    total = len(ids)
    logger.info("候选记录 %d 条 (concurrency=%d)", total, concurrency)
    if total == 0:
        return

    sem = asyncio.Semaphore(concurrency)
    counters = {"migrated": 0, "skipped": 0, "failed": 0}

    async def _wrapped(vs_id):
        async with sem:
            try:
                status, err = await _migrate_one(vs_id)
            except Exception as exc:
                status, err = ("failed", f"未捕获异常: {exc}")
            counters[status] = counters.get(status, 0) + 1
            if status == "failed":
                logger.warning("[migrate] %s failed: %s", vs_id, err)
            elif status == "skipped":
                logger.info("[migrate] %s skipped: %s", vs_id, err)
            done = sum(counters.values())
            if done % 10 == 0 or done == total:
                logger.info("进度 %d/%d  %s", done, total, counters)

    await asyncio.gather(*[_wrapped(i) for i in ids])
    logger.info("完成：%s", counters)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, default=4, help="并发下载/上传任务数")
    parser.add_argument("--limit", type=int, default=None, help="只处理前 N 条（用于试跑）")
    args = parser.parse_args()
    asyncio.run(_run(args.concurrency, args.limit))


if __name__ == "__main__":
    main()
