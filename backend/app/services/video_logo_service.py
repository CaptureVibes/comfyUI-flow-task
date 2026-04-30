"""
视频 Logo 拼接服务

- shared（共享号）/ exclusive（独享号）：拼接 logo_traffic.mp4，原视频音频末尾 1s 淡出，logo 音频 +30dB 并 1s 淡入
- persona（人设号）：拼接 logo_persona.mp4，不调整音量，不淡入
"""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile

import httpx

from app.core.config import settings

logger = logging.getLogger("app.video_logo_service")

_APP_DIR = os.path.join(os.path.dirname(__file__), "..")
_LOGO_PATHS = {
    "shared": os.path.join(_APP_DIR, "logo_traffic.mp4"),
    "exclusive": os.path.join(_APP_DIR, "logo_traffic.mp4"),
    "traffic": os.path.join(_APP_DIR, "logo_traffic.mp4"),  # 兼容旧数据
    "persona": os.path.join(_APP_DIR, "logo_persona.mp4"),
}


async def concat_video_with_logo(source_video_url: str, account_type: str = "traffic") -> str:
    """
    下载源视频，根据 account_type 拼接对应 logo，上传并返回拼接后的 CDN URL。
    """
    logo_path = os.path.abspath(_LOGO_PATHS.get(account_type, _LOGO_PATHS["shared"]))
    if not os.path.isfile(logo_path):
        raise RuntimeError(f"Logo 文件不存在: {logo_path}")

    from app.utils.tmp_storage import disk_tempdir, ensure_free_space
    ensure_free_space(min_bytes=500 * 1024 * 1024, label="logo_concat")
    with disk_tempdir(prefix="logo_concat_") as tmpdir:
        src_path = os.path.join(tmpdir, "source.mp4")
        await _download_video(source_video_url, src_path)

        duration = await _get_duration(src_path)
        if duration <= 0:
            raise RuntimeError(f"无法获取源视频时长: {src_path}")

        out_path = os.path.join(tmpdir, "output.mp4")
        await _ffmpeg_concat(src_path, logo_path, out_path, duration, account_type=account_type)

        cdn_url = await _upload_video(out_path, "logo_concat_output.mp4")

    logger.info("[Logo拼接] 完成 (%s)，CDN URL: %s", account_type, cdn_url[:100])
    return cdn_url


async def _download_video(url: str, dest_path: str) -> None:
    """流式下载视频到本地文件。"""
    async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            with open(dest_path, "wb") as f:
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    f.write(chunk)
    size = os.path.getsize(dest_path)
    logger.info("[Logo拼接] 下载源视频完成: %.1f MB", size / 1024 / 1024)


async def _get_duration(video_path: str) -> float:
    """用 ffprobe 获取视频时长（秒）。"""
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        logger.error("[Logo拼接] ffprobe 失败: %s", stderr.decode()[:500])
        return 0.0
    try:
        return float(stdout.decode().strip())
    except ValueError:
        return 0.0


async def _get_resolution(video_path: str) -> tuple[int, int]:
    """用 ffprobe 获取视频分辨率 (width, height)。"""
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        video_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        logger.error("[Logo拼接] ffprobe resolution 失败: %s", stderr.decode()[:500])
        return 0, 0
    try:
        parts = stdout.decode().strip().split("x")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return 0, 0


async def _ffmpeg_concat(
    src_path: str,
    logo_path: str,
    out_path: str,
    src_duration: float,
    *,
    account_type: str = "traffic",
) -> None:
    """
    用 ffmpeg 拼接视频。

    shared/exclusive: 源音频末尾 1s 淡出，logo 音频 +30dB 并 1s 淡入
    persona: 源音频末尾 1s 淡出，logo 音频原样直接拼接
    """
    fade_out_start = max(0, src_duration - 1.0)

    src_w, src_h = await _get_resolution(src_path)
    if src_w <= 0 or src_h <= 0:
        raise RuntimeError("无法获取源视频分辨率")

    logger.info("[Logo拼接] 源视频分辨率: %dx%d, 类型: %s", src_w, src_h, account_type)

    # logo 缩放到源视频尺寸
    video_filters = (
        f"[0:v]setpts=PTS-STARTPTS[v0];"
        f"[1:v]scale={src_w}:{src_h}:force_original_aspect_ratio=decrease,"
        f"pad={src_w}:{src_h}:(ow-iw)/2:(oh-ih)/2:black,"
        f"setpts=PTS-STARTPTS,setsar=1[v1];"
    )

    # 源音频淡出
    src_audio = f"[0:a]afade=t=out:st={fade_out_start}:d=1[a0];"

    # logo 音频处理
    if account_type in ("traffic", "shared", "exclusive"):
        logo_audio = f"[1:a]volume=30dB,afade=t=in:st=0:d=1[a1];"
    else:
        logo_audio = f"[1:a]anull[a1];"

    filter_complex = (
        video_filters
        + src_audio
        + logo_audio
        + f"[v0][a0][v1][a1]concat=n=2:v=1:a=1[outv][outa]"
    )

    cmd = [
        "ffmpeg", "-y", "-threads", "1",
        "-i", src_path,
        "-i", logo_path,
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "[outa]",
        "-c:v", "libx264",
        "-x264-params", "threads=1",  # libx264 自带线程池，必须单独关
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        out_path,
    ]

    logger.info("[Logo拼接] 开始 ffmpeg 拼接: 源时长=%.1fs, 淡出起始=%.1fs", src_duration, fade_out_start)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        logger.error("[Logo拼接] ffmpeg 失败 (rc=%d): %s", proc.returncode, stderr.decode()[:2000])
        raise RuntimeError(f"ffmpeg concat 失败: {stderr.decode()[:500]}")

    out_size = os.path.getsize(out_path)
    logger.info("[Logo拼接] ffmpeg 拼接完成: %.1f MB", out_size / 1024 / 1024)


async def _upload_video(file_path: str, filename: str) -> str:
    """上传视频文件到 CDN，无限重试。"""
    attempt = 0
    while True:
        attempt += 1
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                with open(file_path, "rb") as f:
                    response = await client.post(
                        settings.video_upload_api_url,
                        files={"file": (filename, f, "video/mp4")},
                        headers={"Accept": "*/*"},
                    )
            if response.status_code >= 400:
                raise RuntimeError(f"Upload API returned {response.status_code}: {response.text[:300]}")
            payload = response.json()
            url = payload.get("data", {}).get("url") if isinstance(payload.get("data"), dict) else None
            if not url:
                raise RuntimeError(f"Upload API response missing data.url: {payload}")
            return url
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            delay = min(attempt * 2, 30)
            logger.warning("[Logo拼接] 上传失败 (attempt %d, %ds后重试): %s", attempt, delay, exc)
            await asyncio.sleep(delay)
