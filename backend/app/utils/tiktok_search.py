"""统一 TikTok 搜索入口

两种搜索模式：
- search_by_keyword: 关键词搜索，RapidAPI 优先，失败时 fallback 到 Apify
- search_by_profiles: 按博主 handle 列表搜索，仅走 Apify（RapidAPI 不支持此模式）

两个函数均返回 list[TikTokVideo]，与 apify.TikTokVideo 数据结构完全一致，
调用方无需关心底层使用了哪个数据源。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.utils.apify import (
    DateRange,
    SearchSorting,
    SortOrder,
    TikTokApifyClient,
    TikTokAuthor,
    TikTokFilter,
    TikTokHashtag,
    TikTokMusic,
    TikTokVideo,
    TikTokVideoMeta,
)

logger = logging.getLogger(__name__)


def _rapid_items_to_tiktok_videos(items: list[dict]) -> list[TikTokVideo]:
    """将 rapid_api.search_videos 返回的 dict 列表转为 TikTokVideo 对象列表。"""
    result = []
    for item in items:
        unique_id = item.get("unique_id", "")
        author = TikTokAuthor(
            id=unique_id,
            name=unique_id,
            nick_name=item.get("nickname") or unique_id,
            profile_url=f"https://www.tiktok.com/@{unique_id}",
            verified=False,
            fans=item.get("follower_count") or 0,
            heart=0,
            video_count=0,
            avatar="",
            private_account=False,
        )
        video_meta = TikTokVideoMeta(
            height=0,
            width=0,
            duration=item.get("duration") or 0,
            cover_url=item.get("cover_url") or "",
            definition="",
            format="",
        )
        result.append(TikTokVideo(
            id=item.get("video_id", ""),
            text=item.get("video_title") or "",
            text_language="",
            create_time=item.get("create_time") or 0,
            create_time_iso="",
            is_ad=False,
            web_video_url=item.get("video_url") or "",
            digg_count=item.get("like_count") or 0,
            share_count=0,
            play_count=item.get("play_count") or 0,
            collect_count=0,
            comment_count=0,
            repost_count=0,
            author=author,
            music=TikTokMusic(music_id="", music_name="", music_author="", play_url="", cover_url=""),
            video_meta=video_meta,
            hashtags=[],
            is_slideshow=False,
            is_pinned=False,
            search_query=None,
        ))
    return result


async def search_by_keyword(
    keyword: str,
    results_per_page: int = 50,
    filter_params: Optional[TikTokFilter] = None,
    oldest_date: Optional[str] = None,
    search_sorting: SearchSorting = SearchSorting.relevance,
) -> list[TikTokVideo]:
    """
    关键词搜索 TikTok 视频。

    优先使用 RapidAPI（更快、无需等待 actor 启动），失败时自动 fallback 到 Apify。
    客户端过滤（filter_params）在两种 source 下均生效。

    Args:
        keyword:          搜索关键词
        results_per_page: 期望返回条数
        filter_params:    客户端二次过滤+排序参数（同 TikTokFilter）
        oldest_date:      最早发布日期 YYYY-MM-DD（仅 Apify 支持，RapidAPI 忽略）
        search_sorting:   搜索排序方式（仅 Apify 支持，RapidAPI 忽略）
    """
    from app.utils import rapid_api

    # --- RapidAPI 尝试（翻页直到凑够 results_per_page 或无更多数据）---
    try:
        all_items: list[dict] = []
        cursor = 0
        while len(all_items) < results_per_page:
            raw = await rapid_api.search_videos(keyword, cursor=cursor)
            all_items.extend(raw["items"])
            if not raw["has_more"] or raw["next_cursor"] == cursor:
                break
            cursor = raw["next_cursor"]
        videos = _rapid_items_to_tiktok_videos(all_items[:results_per_page])
        logger.info("【tiktok_search】keyword=%s RapidAPI 成功，原始=%d条", keyword, len(videos))
    except Exception as exc:
        logger.warning("【tiktok_search】keyword=%s RapidAPI 失败，fallback Apify: %s", keyword, exc)
        apify = TikTokApifyClient()
        videos = await asyncio.to_thread(
            apify.search,
            search_queries=[keyword],
            results_per_page=results_per_page,
            oldest_date=oldest_date,
            search_sorting=search_sorting,
            filter_params=filter_params,
        )
        logger.info("【tiktok_search】keyword=%s Apify fallback 成功，原始=%d条", keyword, len(videos))
        # Apify 内部已做过 filter，直接返回
        return videos

    # RapidAPI 成功后做客户端过滤（复用 Apify 的 _apply_filter）
    if filter_params:
        apify_client = TikTokApifyClient.__new__(TikTokApifyClient)
        videos = apify_client._apply_filter(videos, filter_params)

    logger.info("【tiktok_search】keyword=%s 过滤后=%d条", keyword, len(videos))
    return videos


async def search_by_profiles(
    profiles: list[str],
    results_per_page: int = 50,
    filter_params: Optional[TikTokFilter] = None,
    date_range: DateRange = DateRange.all_time,
    oldest_date: Optional[str] = None,
    newest_date: Optional[str] = None,
    search_sorting: SearchSorting = SearchSorting.relevance,
) -> list[TikTokVideo]:
    """
    按博主 handle 列表搜索视频（仅 Apify 支持，RapidAPI 无此能力）。

    Args:
        profiles:         TikTok 用户名列表（不含 @），如 ["nike", "adidas"]
        results_per_page: 每次请求返回条数
        filter_params:    客户端二次过滤+排序参数
        date_range:       预设时间范围
        oldest_date:      自定义最早日期 YYYY-MM-DD（覆盖 date_range）
        newest_date:      自定义最晚日期 YYYY-MM-DD
        search_sorting:   搜索排序方式
    """
    apify = TikTokApifyClient()
    videos = await asyncio.to_thread(
        apify.search,
        profiles=profiles,
        results_per_page=results_per_page,
        filter_params=filter_params,
        date_range=date_range,
        oldest_date=oldest_date,
        newest_date=newest_date,
        search_sorting=search_sorting,
    )
    logger.info("【tiktok_search】profiles=%s 返回=%d条", profiles, len(videos))
    return videos
