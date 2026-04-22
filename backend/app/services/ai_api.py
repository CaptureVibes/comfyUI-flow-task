"""AI API adapter: uses Google Gemini SDK via GOOGLE_API_KEY from .env.

Usage (text):
    from app.services.ai_api import call_gemini_api
    text = await call_gemini_api(
        model_name="gemini-2.0-flash",
        prompt="...",
        video_url="...",          # optional
        temperature=0.3,
    )

Usage (image gen):
    from app.services.ai_api import generate_image
    img_bytes = await generate_image(
        model_name="gemini-2.0-flash-preview-image-generation",
        prompt="...",
        image_urls=[...],
        aspect_ratio="9:16",
        image_size="1K",
    )
"""
from __future__ import annotations

import logging

from app.services.google_api import call_google_gemini_api, call_google_gemini_api_with_images, generate_image_google, get_google_api_key

logger = logging.getLogger("app.ai_api")


async def call_gemini_api(
    *,
    model_name: str,
    prompt: str,
    temperature: float = 0.3,
    video_url: str | None = None,
    timeout: float = 120.0,
) -> str:
    """Unified text generation via Google Gemini SDK."""
    google_key = get_google_api_key()
    if not google_key:
        raise ValueError("AI API 未配置：请在 .env 中设置 GOOGLE_API_KEY。")

    logger.debug("ai_api: calling Google SDK (model=%s)", model_name)
    return await call_google_gemini_api(
        api_key=google_key,
        model_name=model_name,
        prompt=prompt,
        temperature=temperature,
        video_url=video_url,
        timeout=timeout,
    )


async def call_gemini_api_with_images(
    *,
    model_name: str,
    prompt: str,
    image_urls: list[str],
    temperature: float = 0.3,
    response_schema: dict | None = None,
    timeout: float = 180.0,
) -> str:
    """Text generation with reference images, optionally with JSON schema."""
    google_key = get_google_api_key()
    if not google_key:
        raise ValueError("AI API 未配置：请在 .env 中设置 GOOGLE_API_KEY。")

    logger.debug("ai_api: calling Google SDK with images (model=%s)", model_name)
    return await call_google_gemini_api_with_images(
        api_key=google_key,
        model_name=model_name,
        prompt=prompt,
        image_urls=image_urls,
        temperature=temperature,
        response_schema=response_schema,
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
) -> bytes:
    """Unified image generation via Google Gemini SDK. Returns raw image bytes."""
    google_key = get_google_api_key()
    if not google_key:
        raise ValueError("AI API 未配置：请在 .env 中设置 GOOGLE_API_KEY。")

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
