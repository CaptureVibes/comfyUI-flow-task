"""TikTok 视频下载并上传 CDN

实现：仅走 Apify clockworks/tiktok-scraper actor。
返回值：CDN 永久 URL（字符串）。
"""
from __future__ import annotations

import asyncio
import logging
import os

import httpx

from app.core.config import settings

logger = logging.getLogger("app.tiktok_download")

_APIFY_ACTOR_ID = "GdWCkxBtKWOsKjdch"  # clockworks/tiktok-scraper


def _attach_apify_token(url: str) -> str:
    """对指向 api.apify.com 的 URL 自动拼上 ?token=...。

    Apify 在 shouldDownloadVideos=True 时，会把视频存入 KV store，并把 KV URL
    塞回 dataset 的 videoUrl 字段；该 URL 默认私有，匿名 GET 会 404。
    所有从 Apify 取回的 url 都过这里统一鉴权。
    """
    if not url or "api.apify.com" not in url:
        return url
    token = settings.apify_token
    if not token:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}token={token}"


# ---------------------------------------------------------------------------
# 内部：获取直链
# ---------------------------------------------------------------------------

async def _apify_get_direct_url(tiktok_url: str) -> str:
    """用 clockworks/tiktok-scraper 开启 shouldDownloadVideos，
    从 KV store 拿视频文件 URL。
    """
    if not settings.apify_token:
        raise RuntimeError("APIFY_TOKEN not configured")
    logger.info("apify: calling actor=%s  url=%s", _APIFY_ACTOR_ID, tiktok_url[:80])

    from apify_client import ApifyClient

    def _run_sync() -> str:
        client = ApifyClient(settings.apify_token)
        logger.info("apify: actor.start() ...")
        run_info = client.actor(_APIFY_ACTOR_ID).start(run_input={
            "postURLs": [tiktok_url],
            "resultsPerPage": 1,
            "shouldDownloadVideos": True,
            "shouldDownloadCovers": False,
            "shouldDownloadSlideshowImages": False,
            "shouldDownloadAvatars": False,
            "shouldDownloadMusicCovers": False,
            "downloadSubtitlesOptions": "NEVER_DOWNLOAD_SUBTITLES",
            "commentsPerPost": 0,
        })
        run_id = run_info["id"]
        logger.info("apify: actor started runId=%s, waiting...", run_id)
        run = client.run(run_id).wait_for_finish()
        logger.info("apify: actor finished runId=%s status=%s", run_id, run.get("status"))

        # 先从 dataset 找 videoUrl / downloadUrl
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        logger.info("apify: dataset items=%d", len(items))
        if items:
            item = items[0]
            # 诊断：actor 偶发返回失效 KV URL，把 item 全部字段名 + 几个候选 URL 都打出来便于排障
            logger.info("apify: dataset item keys=%s", sorted(item.keys()))
            for field_name in ("videoUrl", "downloadUrl", "mediaUrls", "videoUrls"):
                v = item.get(field_name)
                if v:
                    logger.info("apify: item.%s=%r", field_name, v)
            video_meta = item.get("videoMeta") or {}
            if video_meta:
                logger.info(
                    "apify: videoMeta keys=%s downloadAddr=%s playAddr=%s",
                    sorted(video_meta.keys()),
                    (video_meta.get("downloadAddr") or "")[:120],
                    (video_meta.get("playAddr") or "")[:120],
                )
            url = (
                item.get("videoUrl")
                or item.get("downloadUrl")
                or (item.get("mediaUrls") or [None])[0]
                or video_meta.get("downloadAddr")
                or video_meta.get("playAddr")
            )
            if url:
                return _attach_apify_token(url)

        # fallback：从 KV store 找视频文件
        kv_store_id = run.get("defaultKeyValueStoreId")
        if kv_store_id:
            kv = client.key_value_store(kv_store_id)
            kv_keys = [r.get("key", "") for r in kv.list_keys().get("items", [])]
            logger.info("apify: KV store keys=%s", kv_keys)
            for key in kv_keys:
                if key.endswith(".mp4") or "video" in key.lower():
                    file_url = (
                        f"https://api.apify.com/v2/key-value-stores/{kv_store_id}"
                        f"/records/{key}"
                    )
                    logger.info("apify: found video in KV store key=%s", key)
                    return _attach_apify_token(file_url)

        raise RuntimeError(f"Apify actor returned no video URL. dataset={len(items)} items")

    url = await asyncio.to_thread(_run_sync)
    logger.info("apify: got direct_url=%s", url)
    return url


# ---------------------------------------------------------------------------
# 内部：流式下载到本地文件
# ---------------------------------------------------------------------------

async def _stream_download(direct_url: str, out_path: str) -> str:
    """将直链视频流式写入 out_path（自动追加 .mp4）。返回实际文件路径。"""
    file_path = out_path if out_path.endswith(".mp4") else out_path + ".mp4"
    async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:
        async with client.stream("GET", direct_url) as resp:
            resp.raise_for_status()
            with open(file_path, "wb") as f:
                async for chunk in resp.aiter_bytes(chunk_size=1024 * 256):
                    f.write(chunk)
    return file_path


# ---------------------------------------------------------------------------
# 内部：上传到 CDN
# ---------------------------------------------------------------------------

async def _upload_to_cdn(file_path: str, filename: str) -> str:
    """上传本地 mp4，返回 URL。后端由 VIDEO_UPLOAD_BACKEND 决定。"""
    from app.utils.video_upload import upload_video_file
    return await upload_video_file(file_path, filename)


# ---------------------------------------------------------------------------
# 公共接口
# ---------------------------------------------------------------------------

async def download_to_file(tiktok_url: str, out_path: str) -> str:
    """下载 TikTok 视频到本地文件，返回实际写入路径（.mp4）。仅走 Apify。"""
    logger.info("tiktok_download: provider=apify url=%s", tiktok_url[:80])
    direct_url = await _apify_get_direct_url(tiktok_url)
    file_path = await _stream_download(direct_url, out_path)
    logger.info("tiktok_download: downloaded path=%s", file_path)
    return file_path


async def download_and_upload(tiktok_url: str, filename: str | None = None) -> str:
    """下载 TikTok 视频并上传到 CDN，返回 CDN 永久 URL。仅走 Apify。"""
    if not filename:
        safe = tiktok_url.rstrip("/").split("/")[-1][:40].replace("?", "_")
        filename = f"{safe}.mp4"

    # 下载到项目级 .tmp（磁盘）而非系统 /tmp（tmpfs/RAM），并预检空间避免连环 ENOSPC
    from app.utils.tmp_storage import disk_tempdir, ensure_free_space
    ensure_free_space(min_bytes=500 * 1024 * 1024, label="tiktok_download")

    with disk_tempdir(prefix="tiktok_dl_") as tmpdir:
        out_template = os.path.join(tmpdir, "video")
        logger.info("tiktok_download: provider=apify url=%s", tiktok_url[:80])
        direct_url = await _apify_get_direct_url(tiktok_url)
        file_path = await _stream_download(direct_url, out_template)
        cdn_url = await _upload_to_cdn(file_path, filename)
        logger.info("tiktok_download: success cdn_url=%s", cdn_url)
        return cdn_url
