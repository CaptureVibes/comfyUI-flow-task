"""统一的视频上传入口。通过 VIDEO_UPLOAD_BACKEND 切换：

  gcs (默认) → 上传到 settings.gcs_bucket_name 下的 gcs_video_prefix 目录，返回 public URL
  cdn        → POST 到 settings.video_upload_api_url，返回 data.url 里的 CDN 链接

三个历史调用点统一收敛到 `upload_video_file(file_path, filename)`：
  - video_source_service._upload_video_file
  - tiktok_download._upload_to_cdn
  - video_task_service._upload_gcs_video_to_cdn
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

import httpx

from app.core.config import settings

logger = logging.getLogger("app.video_upload")


def _today_prefix() -> str:
    """形如 `video-sources/2026-05-20`，按 UTC 日期分桶。"""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    base = (settings.gcs_video_prefix or "video-sources").strip("/")
    return f"{base}/{date_str}"


def _backend() -> str:
    return (settings.video_upload_backend or "gcs").lower()


async def upload_video_file(file_path: str, filename: str) -> str:
    """上传本地视频文件并返回可访问的 URL。

    抛错前会重试，但 4xx 客户端错误直接抛（不可恢复）。
    """
    backend = _backend()
    if backend == "cdn":
        return await _upload_to_cdn_api(file_path, filename)
    if backend == "gcs":
        return await _upload_to_gcs(file_path, filename)
    raise ValueError(f"未知的 VIDEO_UPLOAD_BACKEND: {backend}（只接受 'gcs' / 'cdn'）")


async def _upload_to_gcs(file_path: str, filename: str) -> str:
    """走 google-cloud-storage SDK，返回 public URL。"""
    from app.utils.gcs_utils import upload_video_file_to_gcs

    file_size_mb = os.path.getsize(file_path) / 1024 / 1024
    logger.info("upload_video_file [GCS]: %.1f MB file=%s", file_size_mb, filename)
    attempt = 0
    while True:
        attempt += 1
        try:
            result = await upload_video_file_to_gcs(
                file_path,
                object_prefix=_today_prefix(),
                content_type="video/mp4",
            )
            logger.info(
                "upload_video_file [GCS] done: %s (size=%.1fMB)",
                result.gs_uri, result.size / 1024 / 1024,
            )
            return result.public_url
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if attempt >= 5:
                logger.error("upload_video_file [GCS] 重试 %d 次仍失败: %s", attempt, exc)
                raise
            delay = min(attempt * 2, 30)
            logger.warning("upload_video_file [GCS] failed (attempt %d, %ds 后重试): %s", attempt, delay, exc)
            await asyncio.sleep(delay)


async def _upload_to_cdn_api(file_path: str, filename: str) -> str:
    """POST 到 video_upload_api_url，返回 data.url（旧链路）。"""
    file_size_mb = os.path.getsize(file_path) / 1024 / 1024
    logger.info("upload_video_file [CDN]: %.1f MB file=%s", file_size_mb, filename)
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
            if 400 <= response.status_code < 500:
                raise RuntimeError(
                    f"Upload API returned {response.status_code} (non-retryable, file={file_size_mb:.1f}MB): "
                    f"{response.text[:300]}"
                )
            if response.status_code >= 500:
                raise RuntimeError(f"Upload API returned {response.status_code}: {response.text[:300]}")
            payload = response.json()
            url = payload.get("data", {}).get("url") if isinstance(payload.get("data"), dict) else None
            if not url:
                raise RuntimeError(f"Upload API response missing data.url: {payload}")
            return url
        except asyncio.CancelledError:
            raise
        except RuntimeError as exc:
            if "non-retryable" in str(exc):
                raise
            delay = min(attempt * 2, 30)
            logger.warning("upload_video_file [CDN] failed (attempt %d, %ds 后重试): %s", attempt, delay, exc)
            await asyncio.sleep(delay)
        except Exception as exc:
            delay = min(attempt * 2, 30)
            logger.warning("upload_video_file [CDN] failed (attempt %d, %ds 后重试): %s", attempt, delay, exc)
            await asyncio.sleep(delay)
