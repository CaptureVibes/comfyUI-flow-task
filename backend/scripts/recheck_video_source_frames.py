"""
检测 video_sources.local_video_url 是否真的有视频帧；无帧的重新从 source_url 下载并替换。

背景：之前 RapidAPI 下载偶发产出无帧的视频文件（音频/容器损坏），AI 模板抽帧时
报错。RapidAPI 已经从 tiktok_download.py 下线，现在需要把历史脏数据刷一遍。

用法：
    cd backend

    # 只检测，不修复（输出可疑列表）
    uv run python scripts/recheck_video_source_frames.py --dry-run

    # 限定一定数量先跑一批
    uv run python scripts/recheck_video_source_frames.py --limit 50 --concurrency 3

    # 只针对单条 video_source 复查 + 修复
    uv run python scripts/recheck_video_source_frames.py --video-source-id <uuid>

    # 全量修复（建议先 --dry-run 看规模再决定）
    uv run python scripts/recheck_video_source_frames.py --concurrency 3

判定逻辑：
- 调 ffmpeg 直接读取 local_video_url，尝试抽 1 帧到 stdout（image2pipe → mjpeg）。
- ffmpeg 退出码非 0 / 输出 < 1KB / 60s 超时 → 视为「无视频帧」。
- dry-run：仅打印结果。
- 修复模式：调用现有 _do_download_and_upload(vs_id)，从 source_url 重新下载、压缩、
  上传 CDN，覆盖 local_video_url。失败的会被标记 download_status='failed'。
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import uuid
from typing import Iterable

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models.video_source import VideoSource  # noqa: E402
from app.services.video_source_service import _do_download_and_upload  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scripts.recheck_video_source_frames")

_PROBE_TIMEOUT_SEC = 60.0
_MIN_FRAME_BYTES = 1024  # 一帧 mjpeg 至少这么大才算成功


async def _has_video_frames(url: str) -> tuple[bool, str]:
    """探测 URL 是否能解出至少 1 帧视频。返回 (ok, reason)."""
    if not url:
        return False, "url 为空"
    cmd = [
        "ffmpeg",
        "-y", "-loglevel", "error",
        "-i", url,
        "-frames:v", "1",
        "-f", "image2pipe",
        "-vcodec", "mjpeg",
        "-",
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=_PROBE_TIMEOUT_SEC
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return False, f"ffmpeg 探测超时 {_PROBE_TIMEOUT_SEC:.0f}s"

    if proc.returncode != 0:
        err = (stderr.decode(errors="replace") if stderr else "").strip()[-200:]
        return False, f"ffmpeg rc={proc.returncode}: {err}"
    if len(stdout) < _MIN_FRAME_BYTES:
        return False, f"输出仅 {len(stdout)} 字节 (< {_MIN_FRAME_BYTES})"
    return True, f"frame_size={len(stdout)}"


async def _list_targets(
    *, video_source_id: uuid.UUID | None, limit: int | None
) -> list[VideoSource]:
    async with SessionLocal() as session:
        stmt = (
            select(VideoSource)
            .where(VideoSource.local_video_url.isnot(None))
            .order_by(VideoSource.created_at.asc())
        )
        if video_source_id is not None:
            stmt = stmt.where(VideoSource.id == video_source_id)
        if limit is not None:
            stmt = stmt.limit(limit)
        rows = list((await session.execute(stmt)).scalars().all())
    return rows


async def _process_one(
    vs: VideoSource,
    *,
    dry_run: bool,
    sem: asyncio.Semaphore,
) -> tuple[str, str]:
    """返回 (result, message)。result ∈ {ok, broken_dry, repaired, failed}"""
    async with sem:
        ok, reason = await _has_video_frames(vs.local_video_url or "")
        if ok:
            return "ok", reason
        if dry_run:
            return "broken_dry", reason
        # 修复：调现有下载流程从 source_url 重新拿
        try:
            await _do_download_and_upload(vs.id)
            # 复读 DB 拿最新 local_video_url 再确认一次
            async with SessionLocal() as session:
                fresh = await session.scalar(
                    select(VideoSource).where(VideoSource.id == vs.id)
                )
            if fresh and fresh.local_video_url and fresh.local_video_url != vs.local_video_url:
                ok2, reason2 = await _has_video_frames(fresh.local_video_url)
                if ok2:
                    return "repaired", f"new_url={fresh.local_video_url[:80]} ({reason2})"
                return "failed", f"重下后仍无帧: {reason2}"
            return "failed", "重下后 local_video_url 未更新"
        except Exception as exc:
            return "failed", f"重下异常: {exc}"


async def _drive(targets: Iterable[VideoSource], *, dry_run: bool, concurrency: int) -> dict:
    sem = asyncio.Semaphore(concurrency)
    counts = {"ok": 0, "broken_dry": 0, "repaired": 0, "failed": 0}

    async def _run(vs: VideoSource) -> None:
        result, msg = await _process_one(vs, dry_run=dry_run, sem=sem)
        counts[result] += 1
        tag = {
            "ok": "✓ frames",
            "broken_dry": "✗ broken",
            "repaired": "↻ repaired",
            "failed": "✗ failed",
        }[result]
        logger.info(
            "[%s] vs=%s title=%s | %s",
            tag, vs.id, (vs.video_title or "")[:50], msg,
        )

    await asyncio.gather(*[_run(vs) for vs in targets])
    return counts


async def main() -> None:
    parser = argparse.ArgumentParser(description="复查 video_sources.local_video_url 是否有视频帧；无帧的重新下载")
    parser.add_argument("--dry-run", action="store_true", help="只检测，不重新下载")
    parser.add_argument("--limit", type=int, default=None, help="最多处理多少条")
    parser.add_argument("--concurrency", type=int, default=3, help="并发数（默认 3）")
    parser.add_argument("--video-source-id", type=str, default=None, help="只处理这一条 video_source")
    args = parser.parse_args()

    vs_id = uuid.UUID(args.video_source_id) if args.video_source_id else None
    targets = await _list_targets(video_source_id=vs_id, limit=args.limit)
    logger.info(
        "待处理 video_sources 数: %d (dry_run=%s, concurrency=%d)",
        len(targets), args.dry_run, args.concurrency,
    )
    if not targets:
        return

    counts = await _drive(targets, dry_run=args.dry_run, concurrency=args.concurrency)
    logger.info("=" * 72)
    logger.info(
        "完成 - ok=%d broken=%d repaired=%d failed=%d",
        counts.get("ok", 0),
        counts.get("broken_dry", 0),
        counts.get("repaired", 0),
        counts.get("failed", 0),
    )
    logger.info("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
