"""
Apify TikTok Scraper utility.

Actor: clockworks/tiktok-scraper (GdWCkxBtKWOsKjdch)
Docs:  https://apify.com/clockworks/tiktok-scraper
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from typing import Optional

from apify_client import ApifyClient

from app.core.config import settings

ACTOR_ID = "GdWCkxBtKWOsKjdch"


# ── Enums ─────────────────────────────────────────────────────────────────────

class SortOrder(str, Enum):
    """用于对结果列表排序的字段（value 对应 TikTokVideo 属性名）。"""
    digg_count    = "digg_count"
    play_count    = "play_count"
    share_count   = "share_count"
    collect_count = "collect_count"
    create_time   = "create_time"


class DateRange(str, Enum):
    """预设时间范围（映射到 oldestPostDateUnified）。"""
    one_week  = "1w"
    one_month = "1m"
    three_months = "3m"
    six_months   = "6m"
    one_year  = "1y"
    all_time  = "all"


class SearchSorting(str, Enum):
    """Apify actor 搜索排序方式（searchSorting 字段）。"""
    relevance = "0"
    latest    = "1"
    most_liked = "2"


# ── Sub-models ────────────────────────────────────────────────────────────────

@dataclass
class TikTokAuthor:
    id:             str
    name:           str
    nick_name:      str
    profile_url:    str
    verified:       bool
    fans:           int
    heart:          int
    video_count:    int
    avatar:         str
    private_account: bool

    @classmethod
    def from_dict(cls, d: dict) -> "TikTokAuthor":
        return cls(
            id              = d.get("id", ""),
            name            = d.get("name", ""),
            nick_name       = d.get("nickName", ""),
            profile_url     = d.get("profileUrl", ""),
            verified        = d.get("verified", False),
            fans            = d.get("fans", 0),
            heart           = d.get("heart", 0),
            video_count     = d.get("video", 0),
            avatar          = d.get("avatar", ""),
            private_account = d.get("privateAccount", False),
        )


@dataclass
class TikTokMusic:
    music_id:     str
    music_name:   str
    music_author: str
    play_url:     str
    cover_url:    str

    @classmethod
    def from_dict(cls, d: dict) -> "TikTokMusic":
        return cls(
            music_id     = d.get("musicId", ""),
            music_name   = d.get("musicName", ""),
            music_author = d.get("musicAuthor", ""),
            play_url     = d.get("playUrl", ""),
            cover_url    = d.get("coverMediumUrl", ""),
        )


@dataclass
class TikTokVideoMeta:
    height:    int
    width:     int
    duration:  int
    cover_url: str
    definition: str
    format:    str

    @classmethod
    def from_dict(cls, d: dict) -> "TikTokVideoMeta":
        return cls(
            height     = d.get("height", 0),
            width      = d.get("width", 0),
            duration   = d.get("duration", 0),
            cover_url  = d.get("coverUrl", ""),
            definition = d.get("definition", ""),
            format     = d.get("format", ""),
        )


@dataclass
class TikTokHashtag:
    id:   str
    name: str

    @classmethod
    def from_dict(cls, d: dict) -> "TikTokHashtag":
        return cls(id=d.get("id", ""), name=d.get("name", ""))


@dataclass
class TikTokVideo:
    """单个 TikTok 视频的结构化数据模型。"""
    id:              str
    text:            str
    text_language:   str
    create_time:     int
    create_time_iso: str
    is_ad:           bool
    web_video_url:   str

    digg_count:    int
    share_count:   int
    play_count:    int
    collect_count: int
    comment_count: int
    repost_count:  int

    author:     TikTokAuthor
    music:      TikTokMusic
    video_meta: TikTokVideoMeta
    hashtags:   list[TikTokHashtag]

    is_slideshow: bool
    is_pinned:    bool
    search_query: Optional[str]

    @classmethod
    def from_dict(cls, d: dict) -> "TikTokVideo":
        return cls(
            id              = d.get("id", ""),
            text            = d.get("text", ""),
            text_language   = d.get("textLanguage", ""),
            create_time     = d.get("createTime", 0),
            create_time_iso = d.get("createTimeISO", ""),
            is_ad           = d.get("isAd", False),
            web_video_url   = d.get("webVideoUrl", ""),
            digg_count      = d.get("diggCount", 0),
            share_count     = d.get("shareCount", 0),
            play_count      = d.get("playCount", 0),
            collect_count   = d.get("collectCount", 0),
            comment_count   = d.get("commentCount", 0),
            repost_count    = d.get("repostCount", 0),
            author          = TikTokAuthor.from_dict(d.get("authorMeta", {})),
            music           = TikTokMusic.from_dict(d.get("musicMeta", {})),
            video_meta      = TikTokVideoMeta.from_dict(d.get("videoMeta", {})),
            hashtags        = [TikTokHashtag.from_dict(h) for h in d.get("hashtags", [])],
            is_slideshow    = d.get("isSlideshow", False),
            is_pinned       = d.get("isPinned", False),
            search_query    = d.get("searchQuery"),
        )


# ── Filter / Sort params ──────────────────────────────────────────────────────

@dataclass
class TikTokFilter:
    """客户端二次过滤 + 排序参数。"""
    min_digg:    Optional[int] = None
    max_digg:    Optional[int] = None
    min_play:    Optional[int] = None
    max_play:    Optional[int] = None
    min_share:   Optional[int] = None
    max_share:   Optional[int] = None
    min_collect: Optional[int] = None
    max_collect: Optional[int] = None

    sort_by:         SortOrder = SortOrder.play_count
    sort_descending: bool      = True


def _date_range_to_oldest(date_range: DateRange) -> Optional[str]:
    """将预设时间范围转换为 YYYY-MM-DD 格式的最早发布日期。"""
    today = date.today()
    delta_map = {
        DateRange.one_week:      timedelta(weeks=1),
        DateRange.one_month:     timedelta(days=30),
        DateRange.three_months:  timedelta(days=90),
        DateRange.six_months:    timedelta(days=180),
        DateRange.one_year:      timedelta(days=365),
    }
    if date_range == DateRange.all_time:
        return None
    return (today - delta_map[date_range]).strftime("%Y-%m-%d")


# ── Main client ───────────────────────────────────────────────────────────────

class TikTokApifyClient:
    """
    封装 clockworks/tiktok-scraper actor 的搜索调用。

    支持：
    - 按 username（profiles）搜索博主视频
    - 按关键词（searchQueries）搜索
    - 按 hashtag 搜索
    - 时间范围过滤（date_range 预设 或 自定义 oldest/newest）
    - Apify actor 原生过滤：leastDiggs / mostDiggs
    - 返回后客户端二次过滤：play/share/collect
    - 排序
    """

    def __init__(self, token: str | None = None):
        token = token or settings.apify_token
        if not token:
            raise ValueError("APIFY_TOKEN not set in .env")
        self._client = ApifyClient(token)

    def search(
        self,
        *,
        profiles:      list[str] | None = None,
        search_queries: list[str] | None = None,
        hashtags:      list[str] | None = None,
        results_per_page: int = 50,
        date_range:    DateRange = DateRange.all_time,
        oldest_date:   Optional[str] = None,   # YYYY-MM-DD，优先于 date_range
        newest_date:   Optional[str] = None,   # YYYY-MM-DD
        search_sorting: SearchSorting = SearchSorting.relevance,
        exclude_pinned: bool = False,
        filter_params: Optional[TikTokFilter] = None,
    ) -> list[TikTokVideo]:
        """
        执行搜索并返回过滤+排序后的 TikTokVideo 列表。

        Args:
            profiles:        TikTok 用户名列表（不含 @），如 ["nike", "adidas"]
            search_queries:  关键词列表，如 ["dance challenge"]
            hashtags:        hashtag 列表（不含 #），如 ["fyp"]
            results_per_page: 每次请求返回条数
            date_range:      预设时间范围（DateRange 枚举）
            oldest_date:     自定义最早日期 YYYY-MM-DD（覆盖 date_range）
            newest_date:     自定义最晚日期 YYYY-MM-DD
            search_sorting:  搜索排序方式
            exclude_pinned:  是否排除置顶视频
            filter_params:   客户端二次过滤+排序参数
        """
        # 构建 Apify actor 输入
        run_input: dict = {
            "resultsPerPage":              results_per_page,
            "profileScrapeSections":       ["videos"],
            "profileSorting":              "latest",
            "excludePinnedPosts":          exclude_pinned,
            "scrapeRelatedVideos":         False,
            "shouldDownloadVideos":        False,
            "shouldDownloadCovers":        False,
            "shouldDownloadSlideshowImages": False,
            "shouldDownloadAvatars":       False,
            "shouldDownloadMusicCovers":   False,
            "downloadSubtitlesOptions":    "NEVER_DOWNLOAD_SUBTITLES",
            "commentsPerPost":             0,
            "maxRepliesPerComment":        0,
            "proxyCountryCode":            "None",
        }

        if profiles:
            run_input["profiles"] = profiles
        if hashtags:
            run_input["hashtags"] = hashtags
        if search_queries:
            run_input["searchQueries"] = search_queries
            # actor 要求：使用关键词搜索时必须指定 searchSection = "/video"
            run_input["searchSection"]  = "/video"
            run_input["searchSorting"]  = search_sorting.value

        # 时间范围
        effective_oldest = oldest_date or _date_range_to_oldest(date_range)
        if effective_oldest:
            run_input["oldestPostDateUnified"] = effective_oldest
        if newest_date:
            run_input["newestPostDate"] = newest_date

        # Apify 原生 digg 过滤（减少返回量）
        if filter_params:
            if filter_params.min_digg is not None:
                run_input["leastDiggs"] = filter_params.min_digg
            if filter_params.max_digg is not None:
                run_input["mostDiggs"] = filter_params.max_digg

        import logging
        logger = logging.getLogger("app.apify")
        logger.info(
            "Apify search 开始: profiles=%s queries=%s hashtags=%s results_per_page=%d",
            profiles, search_queries, hashtags, results_per_page,
        )

        # 执行 actor
        run = self._client.actor(ACTOR_ID).call(run_input=run_input)
        raw_items = list(
            self._client.dataset(run["defaultDatasetId"]).iterate_items()
        )
        logger.info("Apify search 完成: 原始结果 %d 条", len(raw_items))

        # 反序列化
        videos = [TikTokVideo.from_dict(item) for item in raw_items]

        # 客户端二次过滤 + 排序
        if filter_params:
            videos = self._apply_filter(videos, filter_params)
            logger.info("Apify search 过滤后: %d 条", len(videos))

        return videos

    def _apply_filter(self, videos: list[TikTokVideo], f: TikTokFilter) -> list[TikTokVideo]:
        def passes(v: TikTokVideo) -> bool:
            if f.min_play    is not None and v.play_count    < f.min_play:    return False
            if f.max_play    is not None and v.play_count    > f.max_play:    return False
            if f.min_share   is not None and v.share_count   < f.min_share:   return False
            if f.max_share   is not None and v.share_count   > f.max_share:   return False
            if f.min_collect is not None and v.collect_count < f.min_collect: return False
            if f.max_collect is not None and v.collect_count > f.max_collect: return False
            return True

        filtered = [v for v in videos if passes(v)]
        filtered.sort(
            key=lambda v: getattr(v, f.sort_by.value),
            reverse=f.sort_descending,
        )
        return filtered
