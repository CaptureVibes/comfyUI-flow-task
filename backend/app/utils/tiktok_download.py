"""TikTok 视频下载并上传 CDN

优先级：tikwm → RapidAPI → Apify
每个 provider 失败后自动 fallback，全部失败则抛出 RuntimeError。
返回值：CDN 永久 URL（字符串）。
"""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile

import httpx

from app.core.config import settings

logger = logging.getLogger("app.tiktok_download")

_TIKWM_BASE = "https://www.tikwm.com/api"
_RAPIDAPI_HOST = "tiktok-api23.p.rapidapi.com"
_RAPIDAPI_BASE = f"https://{_RAPIDAPI_HOST}"
_APIFY_ACTOR_ID = "GdWCkxBtKWOsKjdch"  # clockworks/tiktok-scraper


# ---------------------------------------------------------------------------
# 内部：获取直链
# ---------------------------------------------------------------------------

async def _tikwm_get_direct_url(tiktok_url: str) -> str:
    """tikwm POST /api/ 获取 hdplay/play 直链。"""
    logger.info("tikwm: POST %s/  url=%s", _TIKWM_BASE, tiktok_url[:80])
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(_TIKWM_BASE + "/", data={"url": tiktok_url, "hd": 1})
        resp.raise_for_status()
        body = resp.json()
    code = body.get("code")
    if code != 0:
        raise RuntimeError(f"tikwm error code={code} msg={body.get('msg')}")
    data = body["data"]
    url = data.get("hdplay") or data.get("play")
    if not url:
        raise RuntimeError("tikwm returned no video URL")
    logger.info("tikwm: got direct_url=%s", url[:100])
    return url


async def _rapidapi_get_direct_url(tiktok_url: str) -> str:
    """RapidAPI /api/download/video 获取无水印直链。"""
    if not settings.rapidapi_key:
        raise RuntimeError("RAPIDAPI_KEY not configured")
    logger.info("rapidapi: GET /api/download/video  url=%s", tiktok_url[:80])
    headers = {
        "X-RapidAPI-Key": settings.rapidapi_key,
        "X-RapidAPI-Host": _RAPIDAPI_HOST,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{_RAPIDAPI_BASE}/api/download/video",
            params={"url": tiktok_url},
            headers=headers,
        )
        logger.info("rapidapi: status=%d", resp.status_code)
        resp.raise_for_status()
        body = resp.json()
    data = body.get("data") or body
    url = data.get("hdplay") or data.get("play") or data.get("wmplay") or data.get("video_url")
    if not url:
        raise RuntimeError(f"RapidAPI returned no video URL: {list(body.keys())}")
    logger.info("rapidapi: got direct_url=%s", url[:100])
    return url


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
            url = (
                item.get("videoUrl")
                or item.get("downloadUrl")
                or item.get("videoMeta", {}).get("downloadAddr")
                or item.get("videoMeta", {}).get("playAddr")
            )
            if url:
                return url

        # fallback：从 KV store 找视频文件
        kv_store_id = run.get("defaultKeyValueStoreId")
        if kv_store_id:
            kv = client.key_value_store(kv_store_id)
            for record in kv.list_keys().get("items", []):
                key = record.get("key", "")
                if key.endswith(".mp4") or "video" in key.lower():
                    file_url = f"https://api.apify.com/v2/key-value-stores/{kv_store_id}/records/{key}"
                    logger.info("apify: found video in KV store key=%s", key)
                    return file_url

        raise RuntimeError(f"Apify actor returned no video URL. dataset={len(items)} items")

    url = await asyncio.to_thread(_run_sync)
    logger.info("apify: got direct_url=%s", url[:100])
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
    """上传本地 mp4 到存储 API，返回 CDN 永久 URL。"""
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
            logger.warning("_upload_to_cdn failed (attempt %d, %ds后重试): %s", attempt, delay, exc)
            await asyncio.sleep(delay)


# ---------------------------------------------------------------------------
# 公共接口
# ---------------------------------------------------------------------------

async def download_to_file(tiktok_url: str, out_path: str) -> str:
    """下载 TikTok 视频到本地文件，返回实际写入路径（.mp4）。

    fallback 顺序：tikwm → RapidAPI → Apify
    """
    providers = [
        ("tikwm", _tikwm_get_direct_url),
        ("rapidapi", _rapidapi_get_direct_url),
        ("apify", _apify_get_direct_url),
    ]
    errors: list[str] = []

    for name, get_url_fn in providers:
        try:
            logger.info("tiktok_download: trying provider=%s url=%s", name, tiktok_url[:80])
            direct_url = await get_url_fn(tiktok_url)
            file_path = await _stream_download(direct_url, out_path)
            logger.info("tiktok_download: downloaded provider=%s path=%s", name, file_path)
            return file_path
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            msg = f"{name}: {exc}"
            errors.append(msg)
            logger.warning("tiktok_download: provider=%s failed: %s", name, exc)

    raise RuntimeError(f"All TikTok download providers failed for {tiktok_url}: {'; '.join(errors)}")


async def download_and_upload(tiktok_url: str, filename: str | None = None) -> str:
    """下载 TikTok 视频并上传到 CDN，返回 CDN 永久 URL。

    fallback 顺序：tikwm → RapidAPI → Apify
    """
    if not filename:
        safe = tiktok_url.rstrip("/").split("/")[-1][:40].replace("?", "_")
        filename = f"{safe}.mp4"

    providers = [
        ("tikwm", _tikwm_get_direct_url),
        ("rapidapi", _rapidapi_get_direct_url),
        ("apify", _apify_get_direct_url),
    ]
    errors: list[str] = []

    # 下载到项目级 .tmp（磁盘）而非系统 /tmp（tmpfs/RAM），并预检空间避免连环 ENOSPC
    from app.utils.tmp_storage import disk_tempdir, ensure_free_space
    ensure_free_space(min_bytes=500 * 1024 * 1024, label="tiktok_download")

    with disk_tempdir(prefix="tiktok_dl_") as tmpdir:
        out_template = os.path.join(tmpdir, "video")

        for name, get_url_fn in providers:
            try:
                logger.info("tiktok_download: trying provider=%s url=%s", name, tiktok_url[:80])
                direct_url = await get_url_fn(tiktok_url)
                file_path = await _stream_download(direct_url, out_template)
                cdn_url = await _upload_to_cdn(file_path, filename)
                logger.info("tiktok_download: success provider=%s cdn_url=%s", name, cdn_url)
                return cdn_url
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                msg = f"{name}: {exc}"
                errors.append(msg)
                logger.warning("tiktok_download: provider=%s failed: %s", name, exc)

    raise RuntimeError(f"All TikTok download providers failed for {tiktok_url}: {'; '.join(errors)}")
