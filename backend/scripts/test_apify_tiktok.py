"""
Test app/utils/apify.py — TikTokApifyClient

Usage:
    uv run python scripts/test_apify_tiktok.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.apify import (
    DateRange,
    SearchSorting,
    SortOrder,
    TikTokApifyClient,
    TikTokFilter,
)

client = TikTokApifyClient()

# ── 测试：关键词 + username，最近一个月，按播放量降序 ─────────────────────────
videos = client.search(
    profiles       = ["__ellaward"],
    # search_queries = ["outfit"],
    results_per_page = 10,
    date_range     = DateRange.one_month,
    search_sorting = SearchSorting.latest,
    filter_params  = TikTokFilter(
        min_play    = 10_000,    # 播放 >= 1万
        sort_by     = SortOrder.play_count,
        sort_descending = True,
    ),
)

print(f"Total after filter: {len(videos)}\n")
for i, v in enumerate(videos):
    print(f"{'='*60}")
    print(f"[{i+1}] {v.web_video_url}")
    print(f"  author   : @{v.author.name} ({v.author.fans} fans)")
    print(f"  text     : {v.text[:80]}")
    print(f"  play     : {v.play_count:,}")
    print(f"  digg     : {v.digg_count:,}")
    print(f"  share    : {v.share_count:,}")
    print(f"  collect  : {v.collect_count:,}")
    print(f"  date     : {v.create_time_iso}")
    print(f"  hashtags : {[h.name for h in v.hashtags]}")
