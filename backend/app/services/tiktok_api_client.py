"""
TikTok 第三方 API 客户端

支持 tikwm.com（免费）和 RapidAPI tiktok-api23（付费）两个数据源，
采用 round-robin 轮询 + 单次 fallback 策略：
  - 每次请求按轮询顺序选择 provider
  - 若主 provider 失败，自动尝试另一个
  - 下次请求继续按轮询顺序，不固定在 fallback 上
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import httpx

from app.core.config import settings

logger = logging.getLogger("app.tiktok_api_client")

_TIKWM_BASE = "https://www.tikwm.com/api"
_RAPIDAPI_HOST = "tiktok-api23.p.rapidapi.com"
_RAPIDAPI_BASE = f"https://{_RAPIDAPI_HOST}"

# 全局轮询索引（线程/协程安全性不作严格保证，轻微并发偏差可接受）
_provider_idx: int = 0


def _next_providers() -> tuple[str, str]:
    """返回 (first, second)，first 是本次优先尝试的 provider。"""
    global _provider_idx
    idx = _provider_idx
    _provider_idx += 1
    if idx % 2 == 0:
        return "tikwm", "rapidapi"
    return "rapidapi", "tikwm"


def _extract_video_id(url: str) -> str | None:
    """从 TikTok 视频 URL 中提取纯数字 video ID。"""
    m = re.search(r"/video/(\d+)", url)
    return m.group(1) if m else None


def _extract_username(url: str) -> str | None:
    """从 TikTok 主页 URL 中提取用户名（不含 @）。"""
    m = re.search(r"tiktok\.com/@([\w.\-]+)", url)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# tikwm 原始调用
# ---------------------------------------------------------------------------

async def _tikwm_fetch_video(url: str) -> dict:
    """调用 tikwm POST /api/ 获取视频信息，返回 data 字段内容。"""
    params: dict = {"url": url, "hd": 1}

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(_TIKWM_BASE + "/", data=params)
        resp.raise_for_status()
        body = resp.json()

    if body.get("code") != 0:
        raise RuntimeError(f"tikwm error code={body.get('code')} msg={body.get('msg')}")
    return body["data"]


async def _tikwm_fetch_user(username: str) -> dict:
    """调用 tikwm GET /api/user/info 获取博主信息，返回 data 字段内容。"""
    params: dict = {"unique_id": username}

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(_TIKWM_BASE + "/user/info", params=params)
        resp.raise_for_status()
        body = resp.json()

    if body.get("code") != 0:
        raise RuntimeError(f"tikwm user error code={body.get('code')} msg={body.get('msg')}")
    return body["data"]


# ---------------------------------------------------------------------------
# RapidAPI 原始调用
# ---------------------------------------------------------------------------

def _rapidapi_headers() -> dict:
    return {
        "X-RapidAPI-Key": settings.rapidapi_key,
        "X-RapidAPI-Host": _RAPIDAPI_HOST,
    }


async def _rapidapi_fetch_video(url: str) -> dict:
    """调用 RapidAPI GET /api/post/detail 获取视频信息。"""
    if not settings.rapidapi_key:
        raise RuntimeError("RAPIDAPI_KEY not configured")

    video_id = _extract_video_id(url)
    if not video_id:
        raise RuntimeError(f"Cannot extract video_id from URL: {url}")

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(
            f"{_RAPIDAPI_BASE}/api/post/detail",
            params={"videoId": video_id},
            headers=_rapidapi_headers(),
        )
        resp.raise_for_status()
        body = resp.json()

    # tiktok-api23 一般将视频数据放在 data 或 itemInfo.itemStruct
    data = (
        body.get("data")
        or body.get("itemInfo", {}).get("itemStruct")
        or body
    )
    if not data or not isinstance(data, dict):
        raise RuntimeError(f"Unexpected RapidAPI response structure: {list(body.keys())}")
    return data


async def _rapidapi_fetch_user(username: str) -> dict:
    """调用 RapidAPI GET /api/user/info 获取博主信息。"""
    if not settings.rapidapi_key:
        raise RuntimeError("RAPIDAPI_KEY not configured")

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(
            f"{_RAPIDAPI_BASE}/api/user/info",
            params={"uniqueId": username},
            headers=_rapidapi_headers(),
        )
        resp.raise_for_status()
        body = resp.json()

    data = body.get("data") or body.get("userInfo") or body
    if not data or not isinstance(data, dict):
        raise RuntimeError(f"Unexpected RapidAPI user response structure: {list(body.keys())}")
    return data


# ---------------------------------------------------------------------------
# 字段归一化
# ---------------------------------------------------------------------------

def _normalize_video_from_tikwm(data: dict) -> dict:
    """将 tikwm 视频响应归一化为统一格式。"""
    author = data.get("author") or {}
    unique_id = author.get("unique_id") or ""
    create_ts = data.get("create_time")
    publish_date: datetime | None = None
    if create_ts:
        try:
            publish_date = datetime.fromtimestamp(int(create_ts), tz=timezone.utc)
        except (ValueError, OSError):
            pass

    return {
        "platform": "tiktok",
        "blogger_name": author.get("nickname") or unique_id or None,
        "video_title": data.get("title") or None,
        "video_desc": data.get("title") or None,
        "video_url": data.get("hdplay") or data.get("play") or None,
        "thumbnail_url": data.get("cover") or data.get("origin_cover") or None,
        "view_count": data.get("play_count"),
        "like_count": data.get("digg_count"),
        "comment_count": data.get("comment_count"),
        "share_count": data.get("share_count"),
        "favorite_count": data.get("collect_count"),
        "publish_date": publish_date,
        "duration": data.get("duration"),
        "width": None,
        "height": None,
        "aspect_ratio": None,
        "extra": {
            "extractor_key": "TikTok",
            "uploader_id": author.get("id") or author.get("uid"),
            "uploader": unique_id,
            "channel": author.get("nickname"),
            "uploader_url": f"https://www.tiktok.com/@{unique_id}" if unique_id else None,
            "channel_url": f"https://www.tiktok.com/@{unique_id}" if unique_id else None,
            "_avatar_url": author.get("avatar"),
            "_source": "tikwm",
        },
    }


def _normalize_video_from_rapidapi(data: dict) -> dict:
    """将 RapidAPI tiktok-api23 视频响应归一化为统一格式。
    RapidAPI 返回结构可能是 TikTok itemStruct 格式。
    """
    # itemStruct 格式
    author = data.get("author") or {}
    stats = data.get("stats") or {}
    video_meta = data.get("video") or {}

    unique_id = author.get("uniqueId") or author.get("unique_id") or ""
    nickname = author.get("nickname") or ""
    avatar = author.get("avatarLarger") or author.get("avatarMedium") or author.get("avatar") or ""

    create_ts = data.get("createTime") or data.get("create_time")
    publish_date: datetime | None = None
    if create_ts:
        try:
            publish_date = datetime.fromtimestamp(int(create_ts), tz=timezone.utc)
        except (ValueError, OSError):
            pass

    # 视频直链：RapidAPI 通常在 video.playAddr 或 video.downloadAddr
    video_url = (
        video_meta.get("playAddr")
        or video_meta.get("downloadAddr")
        or data.get("hdplay")
        or data.get("play")
        or None
    )
    cover = (
        video_meta.get("cover")
        or video_meta.get("dynamicCover")
        or data.get("cover")
        or None
    )
    duration = video_meta.get("duration") or data.get("duration")

    return {
        "platform": "tiktok",
        "blogger_name": nickname or unique_id or None,
        "video_title": data.get("desc") or data.get("title") or None,
        "video_desc": data.get("desc") or data.get("title") or None,
        "video_url": video_url,
        "thumbnail_url": cover,
        "view_count": stats.get("playCount") or stats.get("play_count"),
        "like_count": stats.get("diggCount") or stats.get("digg_count"),
        "comment_count": stats.get("commentCount") or stats.get("comment_count"),
        "share_count": stats.get("shareCount") or stats.get("share_count"),
        "favorite_count": stats.get("collectCount") or stats.get("collect_count"),
        "publish_date": publish_date,
        "duration": duration,
        "width": video_meta.get("width"),
        "height": video_meta.get("height"),
        "aspect_ratio": None,
        "extra": {
            "extractor_key": "TikTok",
            "uploader_id": author.get("id") or author.get("uid"),
            "uploader": unique_id,
            "channel": nickname,
            "uploader_url": f"https://www.tiktok.com/@{unique_id}" if unique_id else None,
            "channel_url": f"https://www.tiktok.com/@{unique_id}" if unique_id else None,
            "_avatar_url": avatar or None,
            "_source": "rapidapi",
        },
    }


def _normalize_blogger_from_tikwm(data: dict) -> dict:
    """将 tikwm 用户响应归一化，兼容 _extract_blogger_fields 的输入格式。"""
    user = data.get("user") or data  # tikwm /user/info 有时直接返回 user 对象
    unique_id = user.get("unique_id") or user.get("uniqueId") or ""
    avatar = (
        user.get("avatarLarger") or user.get("avatarMedium")
        or user.get("avatar") or user.get("avatarThumb") or ""
    )
    return {
        "extractor_key": "TikTok",
        "uploader_id": user.get("id") or user.get("uid"),
        "channel_id": user.get("secUid") or user.get("sec_uid"),
        "uploader": unique_id,
        "channel": user.get("nickname"),
        "uploader_url": f"https://www.tiktok.com/@{unique_id}" if unique_id else None,
        "channel_url": f"https://www.tiktok.com/@{unique_id}" if unique_id else None,
        "_avatar_url": avatar or None,
        "_source": "tikwm",
    }


def _normalize_blogger_from_rapidapi(data: dict) -> dict:
    """将 RapidAPI 用户响应归一化，兼容 _extract_blogger_fields 的输入格式。"""
    # data 可能是 { user: {...}, stats: {...} } 或直接是 user 对象
    user = data.get("user") or data
    stats = data.get("stats") or {}
    unique_id = user.get("uniqueId") or user.get("unique_id") or ""
    avatar = (
        user.get("avatarLarger") or user.get("avatarMedium")
        or user.get("avatar") or user.get("avatarThumb") or ""
    )
    return {
        "extractor_key": "TikTok",
        "uploader_id": user.get("id") or user.get("uid"),
        "channel_id": user.get("secUid") or user.get("sec_uid"),
        "uploader": unique_id,
        "channel": user.get("nickname"),
        "uploader_url": f"https://www.tiktok.com/@{unique_id}" if unique_id else None,
        "channel_url": f"https://www.tiktok.com/@{unique_id}" if unique_id else None,
        "_avatar_url": avatar or None,
        "_source": "rapidapi",
        "_follower_count": stats.get("followerCount"),
        "_following_count": stats.get("followingCount"),
        "_video_count": stats.get("videoCount"),
    }


# ---------------------------------------------------------------------------
# 公共接口
# ---------------------------------------------------------------------------

async def fetch_video_info(url: str) -> dict:
    """轮询 tikwm/RapidAPI 获取视频信息。
    返回与 _parse_yt_dlp_info 输出兼容的字段结构。
    """
    first, second = _next_providers()
    errors: list[str] = []

    async def _try_tikwm() -> dict:
        data = await _tikwm_fetch_video(url)
        return _normalize_video_from_tikwm(data)

    async def _try_rapidapi() -> dict:
        data = await _rapidapi_fetch_video(url)
        return _normalize_video_from_rapidapi(data)

    for provider in (first, second):
        try:
            if provider == "tikwm":
                result = await _try_tikwm()
            else:
                result = await _try_rapidapi()
            logger.info("fetch_video_info: provider=%s url=%s", provider, url[:80])
            return result
        except Exception as exc:
            msg = f"{provider}: {exc}"
            errors.append(msg)
            logger.warning("fetch_video_info failed, trying next provider. %s", msg)

    raise RuntimeError(f"All TikTok API providers failed for video {url}: {'; '.join(errors)}")


async def fetch_blogger_info(profile_url: str) -> dict:
    """轮询 tikwm/RapidAPI 获取博主信息。
    返回与 _extract_blogger_fields 输入兼容的字段结构。
    """
    username = _extract_username(profile_url)
    if not username:
        raise RuntimeError(f"Cannot extract username from URL: {profile_url}")

    first, second = _next_providers()
    errors: list[str] = []

    async def _try_tikwm() -> dict:
        data = await _tikwm_fetch_user(username)
        return _normalize_blogger_from_tikwm(data)

    async def _try_rapidapi() -> dict:
        data = await _rapidapi_fetch_user(username)
        return _normalize_blogger_from_rapidapi(data)

    for provider in (first, second):
        try:
            if provider == "tikwm":
                result = await _try_tikwm()
            else:
                result = await _try_rapidapi()
            logger.info("fetch_blogger_info: provider=%s username=%s", provider, username)
            return result
        except Exception as exc:
            msg = f"{provider}: {exc}"
            errors.append(msg)
            logger.warning("fetch_blogger_info failed, trying next provider. %s", msg)

    raise RuntimeError(f"All TikTok API providers failed for blogger {profile_url}: {'; '.join(errors)}")


async def download_video(source_url: str, out_path: str) -> str:
    """获取视频直链后用 httpx 流式下载到 out_path（.mp4）。
    返回实际写入的文件路径。
    """
    # 先拿直链
    info = await fetch_video_info(source_url)
    direct_url = info.get("video_url")
    if not direct_url:
        raise RuntimeError(f"No downloadable video URL returned for {source_url}")

    file_path = out_path if out_path.endswith(".mp4") else out_path + ".mp4"

    logger.info("download_video: downloading from %s -> %s", direct_url[:80], file_path)
    async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:
        async with client.stream("GET", direct_url) as resp:
            resp.raise_for_status()
            with open(file_path, "wb") as f:
                async for chunk in resp.aiter_bytes(chunk_size=1024 * 256):
                    f.write(chunk)

    return file_path
