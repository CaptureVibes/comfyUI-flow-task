"""RapidAPI TikTok 接口封装（tiktok-api23.p.rapidapi.com）

功能：
- search_videos：关键词搜索视频，返回视频列表（含作者信息）
- get_user_info：根据 uniqueId 获取用户信息（含粉丝数）
- 所有请求遇到限流或网络错误时无限重试，每次等待 retry_delay_seconds 秒
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_RAPIDAPI_HOST = "tiktok-api23.p.rapidapi.com"
_BASE_URL = f"https://{_RAPIDAPI_HOST}"
_SEARCH_URL = f"{_BASE_URL}/api/search/video"
_USER_INFO_URL = f"{_BASE_URL}/api/user/info-with-region"


def _make_headers() -> dict[str, str]:
    return {
        "X-RapidAPI-Host": _RAPIDAPI_HOST,
        "X-RapidAPI-Key": settings.rapidapi_key,
    }


# ---------------------------------------------------------------------------
# 内部辅助：遍历嵌套结构提取视频节点
# ---------------------------------------------------------------------------

def _iter_video_items(payload: Any) -> list[dict[str, Any]]:
    """递归遍历 payload，找出所有含 video.id 的节点"""
    candidates: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            video = node.get("video")
            if isinstance(video, dict) and video.get("id"):
                candidates.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return candidates


def _parse_video_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """从搜索响应中解析视频列表，每条包含 video_id/unique_id/duration/follower_count 等"""
    raw_items = _iter_video_items(payload)
    result: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in raw_items:
        video = item.get("video") or {}
        author = item.get("author") or {}
        stats = item.get("stats") or {}

        video_id = str(video.get("id") or "").strip()
        unique_id = str(
            author.get("uniqueId")
            or author.get("unique_id")
            or author.get("authorUniqueId")
            or ""
        ).strip()

        if not video_id or not unique_id or video_id in seen:
            continue
        seen.add(video_id)

        duration = video.get("duration") or video.get("videoDuration") or 0
        try:
            duration = int(duration)
        except (TypeError, ValueError):
            duration = 0

        cover_url = (
            video.get("cover")
            or video.get("originCover")
            or video.get("dynamicCover")
            or None
        )
        play_count = stats.get("playCount") or stats.get("play_count") or 0
        like_count = stats.get("diggCount") or stats.get("digg_count") or 0

        result.append({
            "video_id": video_id,
            "unique_id": unique_id,
            "nickname": str(author.get("nickname") or author.get("nick_name") or unique_id),
            "duration": duration,
            "cover_url": cover_url,
            "play_count": play_count,
            "like_count": like_count,
            # 视频页面 URL，后续可存入数据库
            "video_url": f"https://www.tiktok.com/@{unique_id}/video/{video_id}",
            # 搜索结果里有时带粉丝数（有时没有，需要 get_user_info 补全）
            "follower_count": (
                author.get("followerCount")
                or author.get("fans")
                or None
            ),
            # 原始 title / desc
            "video_title": str(item.get("desc") or ""),
            # 发布时间（Unix 时间戳）
            "create_time": int(item.get("createTime") or item.get("create_time") or 0),
        })

    return result


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------

async def search_videos(
    keyword: str,
    cursor: int = 0,
    retry_delay: float = 5.0,
) -> dict[str, Any]:
    """
    关键词搜索 TikTok 视频。

    返回：
    {
        "items": [{"video_id", "unique_id", "nickname", "duration", ...}, ...],
        "has_more": bool,
        "next_cursor": int,
    }
    遇到限流（429）或网络错误时无限重试。
    """
    params = {
        "keyword": keyword,
        "cursor": cursor,
        "search_id": 0,
    }

    async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
        resp = await client.get(_SEARCH_URL, params=params, headers=_make_headers())

    if resp.status_code != 200:
        logger.warning("【RapidAPI】搜索返回非200 status=%d，keyword=%s", resp.status_code, keyword)
        resp.raise_for_status()

    payload = resp.json()
    items = _parse_video_items(payload)
    has_more = bool(payload.get("hasMore") or payload.get("has_more") or False)
    next_cursor = int(payload.get("cursor") or payload.get("nextCursor") or 0)

    logger.info("【RapidAPI】搜索成功 keyword=%s cursor=%d 返回视频数=%d", keyword, cursor, len(items))
    return {"items": items, "has_more": has_more, "next_cursor": next_cursor}


async def get_user_info(
    unique_id: str,
    retry_delay: float = 5.0,
) -> dict[str, Any]:
    """
    获取 TikTok 用户信息（含粉丝数）。

    返回：
    {
        "unique_id": str,
        "nickname": str,
        "follower_count": int,
        "avatar_url": str | None,
    }
    遇到限流或网络错误时无限重试。
    """
    params = {"uniqueId": unique_id}

    while True:
        try:
            async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
                resp = await client.get(_USER_INFO_URL, params=params, headers=_make_headers())

            if resp.status_code == 429:
                logger.warning("【RapidAPI】获取用户被限流(429)，uniqueId=%s，%.0fs后重试", unique_id, retry_delay)
                await asyncio.sleep(retry_delay)
                continue

            resp.raise_for_status()
            payload = resp.json()

            user_info = payload.get("userInfo") or {}
            user = user_info.get("user") or {}
            stats_v2 = user_info.get("statsV2") or {}
            stats = user_info.get("stats") or {}

            # 优先取精确值（statsV2.followerCount 是字符串）
            raw_followers = stats_v2.get("followerCount") or stats.get("followerCount") or 0
            try:
                follower_count = int(raw_followers)
            except (TypeError, ValueError):
                follower_count = 0

            nickname = str(user.get("nickname") or unique_id)
            avatar_url = user.get("avatarLarger") or user.get("avatarMedium") or user.get("avatarThumb") or None

            logger.info("【RapidAPI】获取用户成功 uniqueId=%s 粉丝数=%d", unique_id, follower_count)
            return {
                "unique_id": unique_id,
                "nickname": nickname,
                "follower_count": follower_count,
                "avatar_url": avatar_url,
            }

        except httpx.HTTPStatusError as exc:
            logger.warning("【RapidAPI】获取用户 HTTP 错误 %d，uniqueId=%s，%.0fs后重试: %s", exc.response.status_code, unique_id, retry_delay, exc)
            await asyncio.sleep(retry_delay)
        except Exception as exc:
            logger.warning("【RapidAPI】获取用户网络异常，uniqueId=%s，%.0fs后重试: %s", unique_id, retry_delay, exc)
            await asyncio.sleep(retry_delay)
