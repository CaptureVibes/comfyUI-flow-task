"""
测试 supplement_templates_for_account 的 Apify 费用。

流程：
1. 查询 account_id 绑定的 tag
2. 用 TikTokApifyClient 模拟一次搜索（不写数据库）
3. 从 Apify run stats 里读取 CU 消耗，换算成美元

Usage:
    uv run python scripts/test_supplement_cost.py
"""
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from apify_client import ApifyClient

from app.core.config import settings

ACCOUNT_ID = uuid.UUID("c673e254-5eae-4b87-a1d3-b247258476b4")
MAX_NEW_VIDEOS = 10
RESULTS_PER_PAGE = MAX_NEW_VIDEOS * 3  # 30

ACTOR_ID = "GdWCkxBtKWOsKjdch"
CU_PRICE_USD = 0.25  # $0.25 per CU


async def get_tag_name() -> str | None:
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.models.account_tag import AccountTag
    from app.models.tag import Tag

    async with SessionLocal() as session:
        stmt = (
            select(Tag.name)
            .join(AccountTag, AccountTag.tag_id == Tag.id)
            .where(AccountTag.account_id == ACCOUNT_ID)
            .order_by(AccountTag.created_at.asc())
            .limit(1)
        )
        return await session.scalar(stmt)


def run_apify_and_get_stats(tag_name: str) -> dict:
    client = ApifyClient(settings.apify_token)

    run_input = {
        "searchQueries":  [tag_name],
        "searchSection":  "/video",
        "searchSorting":  "0",
        "resultsPerPage": RESULTS_PER_PAGE,
        "profileScrapeSections":      ["videos"],
        "profileSorting":             "latest",
        "excludePinnedPosts":         False,
        "scrapeRelatedVideos":        False,
        "shouldDownloadVideos":       False,
        "shouldDownloadCovers":       False,
        "shouldDownloadSlideshowImages": False,
        "shouldDownloadAvatars":      False,
        "shouldDownloadMusicCovers":  False,
        "downloadSubtitlesOptions":   "NEVER_DOWNLOAD_SUBTITLES",
        "commentsPerPost":            0,
        "maxRepliesPerComment":       0,
        "proxyCountryCode":           "None",
    }

    print(f"Starting actor run for keyword='{tag_name}', resultsPerPage={RESULTS_PER_PAGE} ...")
    run = client.actor(ACTOR_ID).call(run_input=run_input)

    # 获取完整 run 信息（含 stats）
    run_detail = client.run(run["id"]).get()
    stats = run_detail.get("stats", {})
    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())

    return {
        "run_id":        run["id"],
        "status":        run["status"],
        "items_count":   len(items),
        "compute_units": stats.get("computeUnits", 0),
        "net_rqu_count": stats.get("netRequestRetries", 0),
        "run_time_secs": stats.get("runTimeSecs", 0),
        "stats_raw":     stats,
    }


async def main():
    print(f"Account ID: {ACCOUNT_ID}")

    tag_name = await get_tag_name()
    if not tag_name:
        print("[ERROR] 该账号没有绑定 tag，无法测试")
        return

    print(f"Tag (keyword): {tag_name}")
    print(f"MAX_NEW_VIDEOS: {MAX_NEW_VIDEOS}  =>  results_per_page: {RESULTS_PER_PAGE}\n")

    result = await asyncio.to_thread(run_apify_and_get_stats, tag_name)

    cu = result["compute_units"]
    cost_usd = cu * CU_PRICE_USD

    print(f"\n{'='*50}")
    print(f"Run ID      : {result['run_id']}")
    print(f"Status      : {result['status']}")
    print(f"Items found : {result['items_count']}")
    print(f"Run time    : {result['run_time_secs']:.1f}s")
    print(f"Compute Units: {cu:.4f} CU")
    print(f"Cost (est.) : ${cost_usd:.4f}  ({cu:.4f} CU × $0.25)")
    print(f"\nRaw stats: {result['stats_raw']}")


if __name__ == "__main__":
    asyncio.run(main())
