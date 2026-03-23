"""
按硬编码关键词搜索 TikTok 视频，并下载当前返回页里的全部结果。

逻辑：
1. 调 RapidAPI 搜索接口
2. 提取当前返回页里的全部视频结果
3. 拼成 TikTok 页面 URL
4. 用 yt-dlp 逐条下载到本地 mp4

用法：
    cd backend
    uv run python scripts/search_and_download_first_tiktok.py
"""
from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import httpx

KEYWORD = "black girl office outfits elianedjema"
RAPIDAPI_HOST = "tiktok-api23.p.rapidapi.com"
RAPIDAPI_KEY = "31251331d9msh840a3f4de5a72afp13ab02jsnb2bcf2e9e2f8"
SEARCH_URL = f"https://{RAPIDAPI_HOST}/api/search/video"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "tmp"


def _iter_candidate_items(payload: Any) -> list[dict[str, Any]]:
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


def _extract_videos(payload: dict[str, Any]) -> list[tuple[str, str]]:
    candidates = _iter_candidate_items(payload)
    if not candidates:
        raise RuntimeError(f"搜索结果里没有找到视频节点: keys={list(payload.keys())}")

    videos: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in candidates:
        video = item.get("video") or {}
        author = item.get("author") or {}

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
        videos.append((video_id, unique_id))

    if not videos:
        raise RuntimeError(f"搜索结果里没有有效的视频 id / 作者: {json.dumps(candidates[:1])[:500]}")

    return videos


async def _search_videos() -> list[tuple[str, str]]:
    headers = {
        "Content-Type": "application/json",
        "X-RapidAPI-Host": RAPIDAPI_HOST,
        "X-RapidAPI-Key": RAPIDAPI_KEY,
    }
    params = {
        "keyword": KEYWORD,
        "cursor": 0,
        "search_id": 0,
    }

    async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
        response = await client.get(SEARCH_URL, params=params, headers=headers)
        print("search_status:", response.status_code)
        response.raise_for_status()
        payload = response.json()

    videos = _extract_videos(payload)
    print("keyword:", KEYWORD)
    print("video_count:", len(videos))
    return videos


def _download_with_ytdlp(video_url: str, output_path: Path) -> None:
    cmd = [
        "yt-dlp",
        "-f",
        "mp4/best",
        "-o",
        str(output_path),
        video_url,
    ]
    print("download_cmd:", " ".join(cmd))
    subprocess.run(cmd, check=True)


async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    videos = await _search_videos()
    for index, (video_id, unique_id) in enumerate(videos, start=1):
        video_url = f"https://www.tiktok.com/@{unique_id}/video/{video_id}"
        output_path = OUTPUT_DIR / f"tiktok_{index:02d}_{video_id}.%(ext)s"

        print(f"[{index}/{len(videos)}] video_page_url:", video_url)
        print(f"[{index}/{len(videos)}] output_template:", str(output_path))
        await asyncio.to_thread(_download_with_ytdlp, video_url, output_path)

    print("done")
    print("saved_dir:", str(OUTPUT_DIR))


if __name__ == "__main__":
    if not shutil.which("yt-dlp"):
        import sys
        print("error: yt-dlp 未安装或不在 PATH 中")
        sys.exit(1)
    asyncio.run(main())
