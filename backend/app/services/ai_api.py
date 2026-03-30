"""AI API adapter: routes calls to Google SDK or EvoLink based on config.

Priority:
  1. If GOOGLE_API_KEY is set in .env → use Google Gemini SDK
  2. Otherwise → fall back to EvoLink REST API

Usage (text):
    from app.services.ai_api import call_gemini_api
    text = await call_gemini_api(
        model_name="gemini-2.0-flash",
        prompt="...",
        video_url="...",          # optional
        temperature=0.3,
        api_key=sys_cfg.evolink_api_key,       # EvoLink fallback
        api_base_url=sys_cfg.evolink_api_base_url,
    )

Usage (image gen):
    from app.services.ai_api import generate_image
    img_bytes = await generate_image(
        model_name="gemini-2.0-flash-preview-image-generation",
        prompt="...",
        image_urls=[...],
        aspect_ratio="9:16",
        image_size="1K",
        api_key=sys_cfg.evolink_api_key,       # EvoLink fallback (Nano2)
        api_base_url=sys_cfg.evolink_api_base_url,
        size=..., quality=...,                 # EvoLink Nano2 params
    )
"""
from __future__ import annotations

import logging

from app.services.google_api import call_google_gemini_api, generate_image_google, get_google_api_key
from app.services.evolink_api import call_evolink_gemini_api

logger = logging.getLogger("app.ai_api")


async def call_gemini_api(
    *,
    model_name: str,
    prompt: str,
    temperature: float = 0.3,
    video_url: str | None = None,
    timeout: float = 120.0,
    # EvoLink fallback params
    api_key: str = "",
    api_base_url: str = "",
) -> str:
    """
    Unified text generation. Picks Google SDK or EvoLink automatically.
    """
    google_key = get_google_api_key()
    if google_key:
        logger.debug("ai_api: routing to Google SDK (model=%s)", model_name)
        return await call_google_gemini_api(
            api_key=google_key,
            model_name=model_name,
            prompt=prompt,
            temperature=temperature,
            video_url=video_url,
            timeout=timeout,
        )

    if not api_key:
        raise ValueError("AI API 未配置：请在 .env 中设置 GOOGLE_API_KEY，或在系统设置中配置 EvoLink API Key。")

    logger.debug("ai_api: routing to EvoLink (model=%s)", model_name)
    return await call_evolink_gemini_api(
        api_base_url=api_base_url,
        api_key=api_key,
        model_name=model_name,
        prompt=prompt,
        temperature=temperature,
        video_url=video_url,
        timeout=timeout,
    )


async def generate_image(
    *,
    model_name: str,
    prompt: str,
    image_urls: list[str],
    aspect_ratio: str = "9:16",
    image_size: str = "1K",
    temperature: float = 1.0,
    # EvoLink / Nano2 fallback params
    api_key: str = "",
    api_base_url: str = "",
    size: str = "9:16",
    quality: str = "1K",
) -> bytes:
    """
    Unified image generation. Returns raw image bytes.

    Google SDK: passes all reference images inline, gets result directly (no polling).
    EvoLink fallback: submits Nano2 job and polls until complete.
    """
    google_key = get_google_api_key()
    if google_key:
        logger.debug("ai_api: image gen via Google SDK (model=%s)", model_name)
        return await generate_image_google(
            api_key=google_key,
            model_name=model_name,
            prompt=prompt,
            image_urls=image_urls,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
            temperature=temperature,
        )

    if not api_key:
        raise ValueError("AI API 未配置：请在 .env 中设置 GOOGLE_API_KEY，或在系统设置中配置 EvoLink API Key。")

    logger.debug("ai_api: image gen via EvoLink Nano2 (model=%s)", model_name)
    from app.services.video_ai_service import _submit_nano2_job, _poll_nano2_task
    import httpx
    task_id = await _submit_nano2_job(
        api_base_url=api_base_url,
        api_key=api_key,
        image_urls=image_urls,
        prompt=prompt,
        model=model_name,
        size=size,
        quality=quality,
    )
    result_url = await _poll_nano2_task(api_base_url=api_base_url, api_key=api_key, task_id=task_id)
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.get(result_url)
        resp.raise_for_status()
        return resp.content
