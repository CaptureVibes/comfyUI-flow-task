"""
最简单的测试脚本：
1. 下载 VIDEO_URL
2. 默认上传到 Gemini Files API，再让 Gemini 做视频理解
3. 也可以切换 URI_MODE 测试 source / GCS URL

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

import httpx


BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

if Path.cwd() != BACKEND_ROOT and (BACKEND_ROOT / ".env").exists():
    os.chdir(BACKEND_ROOT)


# ── 改这里 ─────────────────────────────────────────────────────────
VIDEO_URL = "https://cdn.alvinclub.com/videos/uploads/2026-04-23/92f2bdd35dc4_Links_in_my_bio___cute_Christmas_market_outfit_inspo____BERS.mp4"
MODEL_NAME = "gemini-3.1-pro-preview"
URI_MODE = "file_upload"  # 可选: "file_upload" / "source" / "gs" / "public" / "signed"

PROMPT = "请理解这个视频，描述视频内容，并说明视频是否成功加载。"

BUCKET_NAME = None  # None 表示使用 .env 里的 GCS_BUCKET_NAME
PROJECT_ID = None  # None 表示使用 .env 里的 GCS_PROJECT_ID
OBJECT_PREFIX = "debug/gemini-video-tests"
SIGNED_URL_EXPIRES_MINUTES = 60
# ───────────────────────────────────────────────────────────────────


async def check_url_fetchable(url: str) -> None:
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, trust_env=False) as client:
        response = await client.get(url, headers={"Range": "bytes=0-0"})
    print("url_check_status:", response.status_code)
    print("url_check_content_type:", response.headers.get("content-type"))
    print("url_check_content_range:", response.headers.get("content-range"))
    if response.status_code not in (200, 206):
        print("url_check_body:", response.text[:500])


def file_state_name(file) -> str:
    state = getattr(file, "state", None)
    return getattr(state, "name", None) or getattr(state, "value", None) or str(state)


async def wait_gemini_file_active(client, file_name: str):
    for _ in range(30):
        file = await client.aio.files.get(name=file_name)
        state = file_state_name(file)
        print("gemini_file_state:", state)
        if state == "ACTIVE":
            return file
        if state == "FAILED":
            raise RuntimeError(f"Gemini file processing failed: {file}")
        await asyncio.sleep(2)
    raise RuntimeError("Gemini file processing timeout")


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    from app.core.config import settings
    from app.utils.gcs_utils import (
        download_video_to_temp_file,
        generate_gcs_signed_url,
        upload_video_file_to_gcs,
    )
    from google import genai
    from google.genai import types

    if not VIDEO_URL or VIDEO_URL == "PASTE_VIDEO_URL_HERE":
        raise RuntimeError("请先在脚本顶部设置 VIDEO_URL")
    if not settings.google_api_key:
        raise RuntimeError("请先在 backend/.env 中设置 GOOGLE_API_KEY")

    print("source_url:", VIDEO_URL)

    client = genai.Client(api_key=settings.google_api_key)

    if URI_MODE == "file_upload":
        downloaded = await download_video_to_temp_file(VIDEO_URL)
        print("download_final_url:", downloaded.final_url)
        print("download_content_type:", downloaded.content_type)
        print("download_size:", downloaded.size)

        try:
            gemini_file = await client.aio.files.upload(
                file=downloaded.path,
                config=types.UploadFileConfig(
                    mimeType=downloaded.content_type,
                    displayName=downloaded.filename,
                ),
            )
            print("gemini_file_name:", gemini_file.name)
            print("gemini_file_uri:", gemini_file.uri)
            print("gemini_file_mime_type:", gemini_file.mime_type)
            gemini_file = await wait_gemini_file_active(client, gemini_file.name)
            gemini_video_uri = gemini_file.uri
            video_mime_type = gemini_file.mime_type or downloaded.content_type or "video/mp4"
        finally:
            downloaded.path.unlink(missing_ok=True)
    elif URI_MODE == "source":
        gemini_video_uri = VIDEO_URL
        video_mime_type = "video/mp4"
    else:
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
            try:
                gemini_video_uri = generate_gcs_signed_url(
                    bucket_name=uploaded.bucket_name,
                    object_key=uploaded.object_key,
                    project_id=PROJECT_ID,
                    expiration_minutes=SIGNED_URL_EXPIRES_MINUTES,
                )
            except Exception as exc:
                raise RuntimeError(
                    "生成 signed URL 失败。通常是因为当前 ADC 是 gcloud 用户凭证，"
                    "不是 service account key，无法签名。可以改用 service account "
                    "GOOGLE_APPLICATION_CREDENTIALS，或者把 URI_MODE 改回 public 并确保对象公开可访问。"
                ) from exc
        else:
            raise RuntimeError(f"不支持的 URI_MODE: {URI_MODE}")
        video_mime_type = uploaded.content_type or "video/mp4"

    print("gemini_video_uri:", gemini_video_uri)
    if URI_MODE != "file_upload":
        await check_url_fetchable(gemini_video_uri)
    print("calling_gemini: start")

    response = await client.aio.models.generate_content(
        model=MODEL_NAME,
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_uri(
                        file_uri=gemini_video_uri,
                        mime_type=video_mime_type,
                    ),
                    types.Part.from_text(text=PROMPT),
                ],
            )
        ],
        config=types.GenerateContentConfig(temperature=0.2),
    )

    print("calling_gemini: ok")
    print("gemini_response:")
    print(response.text)


if __name__ == "__main__":
    asyncio.run(main())
