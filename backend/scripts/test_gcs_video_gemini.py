"""
最简单的测试脚本：
1. 下载 VIDEO_URL
2. 上传到 GCS
3. 把 GCS 视频 URI 发给 Gemini 做视频理解

用法：
    cd backend
    .venv/bin/python scripts/test_gcs_video_gemini.py
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

if Path.cwd() != BACKEND_ROOT and (BACKEND_ROOT / ".env").exists():
    os.chdir(BACKEND_ROOT)


# ── 改这里 ─────────────────────────────────────────────────────────
VIDEO_URL = "https://cdn.alvinclub.com/videos/uploads/2026-04-23/92f2bdd35dc4_Links_in_my_bio___cute_Christmas_market_outfit_inspo____BERS.mp4"
MODEL_NAME = "gemini-3.1-pro-preview"
URI_MODE = "public"  # 可选: "gs" / "public" / "signed"

PROMPT = "请理解这个视频，描述视频内容，并说明视频是否成功加载。"

BUCKET_NAME = None  # None 表示使用 .env 里的 GCS_BUCKET_NAME
PROJECT_ID = None  # None 表示使用 .env 里的 GCS_PROJECT_ID
OBJECT_PREFIX = "debug/gemini-video-tests"
SIGNED_URL_EXPIRES_MINUTES = 60
# ───────────────────────────────────────────────────────────────────


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    from app.core.config import settings
    from app.services.ai_api import call_gemini_api
    from app.utils.gcs_utils import (
        download_video_to_temp_file,
        generate_gcs_signed_url,
        upload_video_file_to_gcs,
    )

    if not VIDEO_URL or VIDEO_URL == "PASTE_VIDEO_URL_HERE":
        raise RuntimeError("请先在脚本顶部设置 VIDEO_URL")
    if not settings.google_api_key:
        raise RuntimeError("请先在 backend/.env 中设置 GOOGLE_API_KEY")

    print("source_url:", VIDEO_URL)

    downloaded = await download_video_to_temp_file(VIDEO_URL)
    print("download_final_url:", downloaded.final_url)
    print("download_content_type:", downloaded.content_type)
    print("download_size:", downloaded.size)

    try:
        uploaded = await upload_video_file_to_gcs(
            downloaded.path,
            object_prefix=OBJECT_PREFIX,
            bucket_name=BUCKET_NAME,
            project_id=PROJECT_ID,
            content_type=downloaded.content_type,
        )
    finally:
        downloaded.path.unlink(missing_ok=True)

    print("gcs_uri:", uploaded.gs_uri)
    print("gcs_public_url:", uploaded.public_url)
    print("gcs_content_type:", uploaded.content_type)
    print("gcs_size:", uploaded.size)

    if URI_MODE == "gs":
        gemini_video_uri = uploaded.gs_uri
    elif URI_MODE == "public":
        gemini_video_uri = uploaded.public_url
    elif URI_MODE == "signed":
        gemini_video_uri = generate_gcs_signed_url(
            bucket_name=uploaded.bucket_name,
            object_key=uploaded.object_key,
            project_id=PROJECT_ID,
            expiration_minutes=SIGNED_URL_EXPIRES_MINUTES,
        )
    else:
        raise RuntimeError(f"不支持的 URI_MODE: {URI_MODE}")

    print("gemini_video_uri:", gemini_video_uri)
    print("calling_gemini: start")

    response = await call_gemini_api(
        model_name=MODEL_NAME,
        prompt=PROMPT,
        video_url=gemini_video_uri,
        temperature=0.2,
        timeout=180.0,
    )

    print("calling_gemini: ok")
    print("gemini_response:")
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
