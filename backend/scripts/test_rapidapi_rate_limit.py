"""
测试 RapidAPI TikTok 搜索接口的限流情况。

10 个关键词并发，每个关键词每隔 0.2 秒调用一次，持续翻页，
实时打印每次请求状态码、耗时、限流率。Ctrl+C 终止后打印汇总。

用法：
    cd backend
    uv run python scripts/test_rapidapi_rate_limit.py
"""
from __future__ import annotations

import asyncio
import time

import httpx

KEYWORDS = [
    "what i wear in a week realistic",
    "corporate girl week of outfits",
    "midsize ootw",
    "fall weekly lookbook inspo",
    "capsule wardrobe 7 days",
    "#whatiworethisweek",
    "clean girl aesthetic outfit rotation",
    "teacher outfits of the week",
    "styling basics for a week",
    "petite everyday outfits week",
    "black girl office outfits",
    "summer dress haul try on",
    "streetwear lookbook men",
    "aesthetic outfit ideas",
    "korean fashion inspo",
    "gym workout outfit women",
    "casual date night outfit",
    "vintage thrift haul",
    "plus size fashion ootd",
    "minimalist wardrobe essentials",
]

RAPIDAPI_HOST = "tiktok-api23.p.rapidapi.com"
RAPIDAPI_KEY = "31251331d9msh840a3f4de5a72afp13ab02jsnb2bcf2e9e2f8"
SEARCH_URL = f"https://{RAPIDAPI_HOST}/api/search/video"

INTERVAL = 1  # 每个关键词的请求间隔（秒）
CONCURRENCY = 10  # 并发数，取 KEYWORDS 前 N 个

# 共享计数器（所有协程累加）
request_count = 0
non_200_count = 0
status_counts: dict[int, int] = {}
start_time = 0.0
print_lock = asyncio.Lock()


async def search_loop(client: httpx.AsyncClient, keyword: str, worker_id: int) -> None:
    global request_count, non_200_count

    headers = {
        "Content-Type": "application/json",
        "X-RapidAPI-Host": RAPIDAPI_HOST,
        "X-RapidAPI-Key": RAPIDAPI_KEY,
    }

    cursor = 0
    search_id = 0

    while True:
        params = {
            "keyword": keyword,
            "cursor": cursor,
            "search_id": search_id,
        }

        elapsed = time.time() - start_time
        req_start = time.time()
        try:
            resp = await client.get(SEARCH_URL, params=params, headers=headers)
            latency = time.time() - req_start
            code = resp.status_code

            async with print_lock:
                request_count += 1
                status_counts[code] = status_counts.get(code, 0) + 1
                if code != 200:
                    non_200_count += 1
                req_no = request_count
                rate = non_200_count / req_no * 100

            note = ""
            if code == 200:
                try:
                    data = resp.json()
                    has_more = data.get("has_more", 0)
                    new_cursor = data.get("cursor", cursor)
                    new_search_id = data.get("search_id", search_id)
                    note = f"has_more={has_more} next_cursor={new_cursor}"
                    if has_more:
                        cursor = new_cursor
                        search_id = new_search_id
                    else:
                        note += " (reset)"
                        cursor = 0
                except Exception:
                    note = "json parse error"
            else:
                note = resp.text[:60] if resp.text else ""

            print(f"{req_no:>4}  W{worker_id:<2}  {code:>6}  {latency:>7.2f}s  {elapsed:>7.1f}s  {non_200_count:>7}  {rate:>5.1f}%  {keyword[:25]:<25}  {note}")

        except httpx.RequestError as e:
            latency = time.time() - req_start
            async with print_lock:
                request_count += 1
                non_200_count += 1
                status_counts[-1] = status_counts.get(-1, 0) + 1
                req_no = request_count
                rate = non_200_count / req_no * 100
            print(f"{req_no:>4}  W{worker_id:<2}  {'ERR':>6}  {latency:>7.2f}s  {elapsed:>7.1f}s  {non_200_count:>7}  {rate:>5.1f}%  {keyword[:25]:<25}  {e}")

        await asyncio.sleep(INTERVAL)


async def main() -> None:
    global start_time
    start_time = time.time()

    active_keywords = KEYWORDS[:CONCURRENCY]
    print(f"concurrency: {len(active_keywords)} / {len(KEYWORDS)}")
    print(f"interval: {INTERVAL}s per worker")
    print(f"{'#':>4}  {'wk':<3}  {'status':>6}  {'latency':>8}  {'elapsed':>8}  {'non200':>7}  {'rate':>6}  {'keyword':<25}  note")
    print("-" * 115)

    async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
        tasks = [
            asyncio.create_task(search_loop(client, kw, i))
            for i, kw in enumerate(active_keywords)
        ]
        try:
            await asyncio.gather(*tasks)
        except (KeyboardInterrupt, asyncio.CancelledError):
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    total_time = time.time() - start_time
    print("\n" + "=" * 80)
    print("Summary")
    print(f"  workers:        {len(active_keywords)}")
    print(f"  total requests: {request_count}")
    print(f"  total time:     {total_time:.1f}s")
    print(f"  status codes:")
    for code, count in sorted(status_counts.items()):
        label = "network_error" if code == -1 else str(code)
        pct = count / request_count * 100
        print(f"    {label}: {count} ({pct:.1f}%)")
    print(f"  non-200 total: {non_200_count} / {request_count} = {non_200_count / max(request_count, 1) * 100:.1f}%")


if __name__ == "__main__":
    asyncio.run(main())
