from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.video_source import VideoSource
from app.models.video_source_stat import VideoSourceStat

logger = logging.getLogger("app.video_stats_collector")

_stats_collector_task: asyncio.Task | None = None
_stats_collector_stop_event: asyncio.Event | None = None

# Concurrency limit for re-parsing videos
_STATS_CONCURRENCY = 5


def start_video_stats_collector() -> None:
    global _stats_collector_task, _stats_collector_stop_event
    if _stats_collector_task is not None and not _stats_collector_task.done():
        return
    loop = asyncio.get_running_loop()
    _stats_collector_stop_event = asyncio.Event()
    _stats_collector_task = loop.create_task(_collector_loop(_stats_collector_stop_event))
    logger.info("Video stats collector started")


async def stop_video_stats_collector() -> None:
    global _stats_collector_task, _stats_collector_stop_event
    stop_event = _stats_collector_stop_event
    worker = _stats_collector_task
    _stats_collector_stop_event = None
    _stats_collector_task = None

    if stop_event is not None:
        stop_event.set()
    if worker is None:
        return
    worker.cancel()
    try:
        await worker
    except asyncio.CancelledError:
        pass
    logger.info("Video stats collector stopped")


async def _collector_loop(stop_event: asyncio.Event) -> None:
    try:
        while not stop_event.is_set():
            try:
                await _run_collection_if_due()
            except Exception:
                logger.exception("Stats collection run failed")

            # Calculate seconds until next midnight UTC
            now = datetime.now(timezone.utc)
            tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            seconds_until_midnight = (tomorrow - now).total_seconds()
            logger.info("Next stats collection at midnight UTC: in %d seconds", seconds_until_midnight)

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=seconds_until_midnight)
            except asyncio.TimeoutError:
                continue
    except asyncio.CancelledError:
        raise


async def _run_collection_if_due() -> None:
    now = datetime.now(timezone.utc)
    # Run only if we're within the first minute after midnight (00:00:00 - 00:01:00 UTC)
    if now.hour != 0 or now.minute != 0:
        logger.debug("Not midnight yet, skipping stats collection")
        return

    logger.info("Starting daily video stats collection")
    async with SessionLocal() as session:
        stmt = select(VideoSource.id, VideoSource.source_url).order_by(VideoSource.id)
        rows = (await session.execute(stmt)).all()

    if not rows:
        logger.info("No video sources to collect stats for")
        return

    logger.info("Collecting stats for %d video sources", len(rows))
    semaphore = asyncio.Semaphore(_STATS_CONCURRENCY)

    tasks = [
        _collect_one(vs_id, source_url, semaphore)
        for vs_id, source_url in rows
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    success_count = sum(1 for r in results if r is True)
    error_count = len(results) - success_count
    logger.info("Stats collection complete: %d success, %d errors", success_count, error_count)


async def _collect_one(
    vs_id: str,
    source_url: str,
    semaphore: asyncio.Semaphore,
) -> bool:
    async with semaphore:
        try:
            await _parse_and_save_stats(vs_id, source_url)
            return True
        except Exception as exc:
            logger.warning("Failed to collect stats for video %s: %s", vs_id, exc)
            return False


async def _parse_and_save_stats(vs_id: str, source_url: str) -> None:
    if "tiktok.com" in source_url or "vm.tiktok.com" in source_url:
        from app.services import tiktok_api_client
        parsed = await tiktok_api_client.fetch_video_info(source_url)
    else:
        from app.services.video_source_service import _parse_yt_dlp_info

        def _run() -> dict:
            try:
                import yt_dlp  # type: ignore
            except ImportError:
                raise RuntimeError("yt-dlp is not installed")
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "format": "best",
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(source_url, download=False)
            return info or {}

        info = await asyncio.to_thread(_run)
        parsed = _parse_yt_dlp_info(info)

    async with SessionLocal() as session:
        # Save historical snapshot
        stat = VideoSourceStat(
            video_source_id=vs_id,
            collected_at=datetime.now(timezone.utc),
            view_count=parsed.get("view_count"),
            like_count=parsed.get("like_count"),
            favorite_count=parsed.get("favorite_count"),
            comment_count=parsed.get("comment_count"),
            share_count=parsed.get("share_count"),
        )
        session.add(stat)

        # Update current counts in video_sources table
        vs = await session.get(VideoSource, vs_id)
        if vs:
            vs.view_count = parsed.get("view_count")
            vs.like_count = parsed.get("like_count")
            vs.favorite_count = parsed.get("favorite_count")
            vs.comment_count = parsed.get("comment_count")
            vs.share_count = parsed.get("share_count")

        await session.commit()
