"""Google Gemini SDK client (google-genai) — text generation + image generation."""
from __future__ import annotations

import asyncio
import base64
import logging

from google import genai
from google.genai import types

logger = logging.getLogger("app.google_api")


def get_google_api_key() -> str:
    """Return GOOGLE_API_KEY from settings (loaded from .env), or empty string if not set."""
    from app.core.config import settings
    return settings.google_api_key


def _make_client(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key)


# =============================================================================
# 文本生成（支持可选视频/图片 URL）
# =============================================================================

async def call_google_gemini_api(
    *,
    api_key: str,
    model_name: str,
    prompt: str,
    temperature: float = 0.3,
    video_url: str | None = None,
    response_schema: dict | None = None,
    timeout: float = 120.0,
) -> str:
    """
    Call Google Gemini SDK for text generation.

    Supports text-only and video+text calls (via file URI).
    Pass response_schema (JSON Schema dict) to enable structured JSON output.
    Returns extracted text content. Retries on transient errors.
    """
    client = _make_client(api_key)

    parts: list[types.Part] = []
    if video_url:
        parts.append(types.Part.from_uri(file_uri=video_url, mime_type="video/mp4"))
    parts.append(types.Part.from_text(text=prompt))

    config_kwargs: dict = {"temperature": temperature}
    if response_schema is not None:
        config_kwargs["response_mime_type"] = "application/json"
        config_kwargs["response_schema"] = response_schema
    config = types.GenerateContentConfig(**config_kwargs)

    masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
    logger.info(
        "Google SDK text request: model=%s, api_key=%s, video=%s, prompt=%s",
        model_name, masked_key, bool(video_url), prompt[:200],
    )

    attempt = 0
    max_attempts = 3
    while attempt < max_attempts:
        attempt += 1
        try:
            response = await client.aio.models.generate_content(
                model=model_name,
                contents=[types.Content(role="user", parts=parts)],
                config=config,
            )
            text = response.text
            logger.info("Google SDK text response: %s", (text or "")[:500])
            return text or ""

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # 4xx 不重试（配置错误）
            exc_str = str(exc)
            if any(code in exc_str for code in ["400", "401", "403", "404"]):
                logger.error(
                    "Google SDK 4xx error (不重试): model=%s video=%s prompt=%s\n%s",
                    model_name, video_url, prompt[:300], exc,
                )
                raise
            if attempt >= max_attempts:
                logger.error("Google SDK text 已达最大重试次数 %d，放弃: model=%s %s", max_attempts, model_name, exc)
                raise
            delay = min(attempt * 2, 30)
            logger.warning("Google SDK text attempt %d/%d failed (%ds后重试): %s", attempt, max_attempts, delay, exc)
            await asyncio.sleep(delay)


# =============================================================================
# 图片生成（多参考图 → 生成一张图，返回 base64 bytes）
# =============================================================================

async def call_google_gemini_api_with_images(
    *,
    api_key: str,
    model_name: str,
    prompt: str,
    image_urls: list[str],
    temperature: float = 0.3,
    response_schema: dict | None = None,
    timeout: float = 180.0,
) -> str:
    """
    Call Google Gemini SDK for text generation with reference images.

    Supports structured JSON output via response_schema (passed as dict).
    Returns extracted text content.
    """
    client = _make_client(api_key)

    parts: list[types.Part] = []
    for i, url in enumerate(image_urls):
        parts.append(types.Part.from_text(text=f"参考图{i + 1}"))
        parts.append(types.Part.from_uri(file_uri=url, mime_type="image/jpeg"))
    parts.append(types.Part.from_text(text=prompt))

    config_kwargs: dict = {"temperature": temperature}
    if response_schema is not None:
        config_kwargs["response_mime_type"] = "application/json"
        config_kwargs["response_schema"] = response_schema

    config = types.GenerateContentConfig(**config_kwargs)

    logger.info(
        "Google SDK text+images request: model=%s, images=%d, schema=%s, prompt=%s",
        model_name, len(image_urls), bool(response_schema), prompt[:200],
    )

    attempt = 0
    max_attempts = 3
    while attempt < max_attempts:
        attempt += 1
        try:
            response = await client.aio.models.generate_content(
                model=model_name,
                contents=[types.Content(role="user", parts=parts)],
                config=config,
            )
            text = response.text
            logger.info("Google SDK text+images response: %s", (text or "")[:500])
            return text or ""

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            exc_str = str(exc)
            if any(code in exc_str for code in ["400", "401", "403", "404"]):
                logger.error("Google SDK 4xx error (不重试): model=%s %s", model_name, exc)
                raise
            if attempt >= max_attempts:
                logger.error("Google SDK text+images 已达最大重试次数 %d，放弃: %s", max_attempts, exc)
                raise
            delay = min(attempt * 2, 30)
            logger.warning("Google SDK text+images attempt %d/%d failed (%ds后重试): %s", attempt, max_attempts, delay, exc)
            await asyncio.sleep(delay)


async def generate_image_google(
    *,
    api_key: str,
    model_name: str,
    prompt: str,
    image_urls: list[str],
    aspect_ratio: str = "9:16",
    image_size: str = "1K",
    temperature: float = 1.0,
) -> bytes:
    """
    Generate an image using Google Gemini SDK with reference images.

    Passes all reference images + prompt to the model with response_modalities=['IMAGE'].
    Returns raw image bytes (PNG/JPEG).
    """
    client = _make_client(api_key)

    parts: list[types.Part] = []
    for i, url in enumerate(image_urls):
        parts.append(types.Part.from_text(text=f"参考图{i + 1}"))
        parts.append(types.Part.from_uri(file_uri=url, mime_type="image/jpeg"))
    parts.append(types.Part.from_text(text=prompt))

    config = types.GenerateContentConfig(
        temperature=temperature,
        response_modalities=["IMAGE"],
        image_config=types.ImageConfig(
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        ),
    )

    logger.info(
        "Google SDK image gen: model=%s, images=%d, aspect_ratio=%s, image_size=%s, prompt=%s",
        model_name, len(image_urls), aspect_ratio, image_size, prompt[:200],
    )

    attempt = 0
    max_attempts = 10
    while attempt < max_attempts:
        attempt += 1
        try:
            response = await client.aio.models.generate_content(
                model=model_name,
                contents=[types.Content(role="user", parts=parts)],
                config=config,
            )

            # 从响应中提取图片 bytes
            for candidate in response.candidates or []:
                for part in (candidate.content.parts or []):
                    if part.inline_data and part.inline_data.data:
                        data = part.inline_data.data
                        # SDK 可能返回 bytes 或 base64 字符串
                        if isinstance(data, (bytes, bytearray)):
                            logger.info("Google SDK image gen success: %d bytes", len(data))
                            return bytes(data)
                        else:
                            raw = base64.b64decode(data)
                            logger.info("Google SDK image gen success (b64): %d bytes", len(raw))
                            return raw

            # 检查是否被内容安全策略拦截，拦截时无需重试
            prompt_feedback = getattr(response, "prompt_feedback", None)
            block_reason = getattr(prompt_feedback, "block_reason", None) if prompt_feedback else None
            if block_reason:
                logger.error("Google SDK image gen blocked (不重试): block_reason=%s", block_reason)
                raise ValueError(f"Google SDK image gen: blocked by safety filter — block_reason={block_reason}")
            raise ValueError(f"Google SDK image gen: no image in response — {response}")

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            exc_str = str(exc)
            if any(code in exc_str for code in ["400", "401", "403", "404"]):
                logger.error("Google SDK image gen 4xx (不重试): %s", exc)
                raise
            if "blocked by safety filter" in exc_str:
                raise
            if attempt >= max_attempts:
                logger.error("Google SDK image gen 已达最大重试次数 %d，放弃: %s", max_attempts, exc)
                raise
            delay = min(attempt * 2, 30)
            logger.warning("Google SDK image gen attempt %d/%d failed (%ds后重试): %s", attempt, max_attempts, delay, exc)
            await asyncio.sleep(delay)
