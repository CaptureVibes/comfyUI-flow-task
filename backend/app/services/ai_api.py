"""AI API adapter: Google Gemini SDK 优先；quota 重试耗尽后 fallback 到 Evolink。

Usage (text):
    from app.services.ai_api import call_gemini_api
    text = await call_gemini_api(
        model_name="gemini-2.0-flash",
        prompt="...",
        video_url="...",          # optional；video 输入不支持 Evolink fallback
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

Fallback 规则（与用户决策一致）：
- Google 内部已有 _QUOTA_MAX_RETRIES=15 的 429 重试，重试到顶后抛出。
- ai_api 这层捕获该最终 quota 异常 → 转向 Evolink；非 quota 错误原样抛出。
- video_url 场景下不 fallback（Evolink OpenAI 兼容口不接受 video）。
- EVOLINK_API_KEY 未配置时也不 fallback，保持原 Google 异常向上抛。
"""
from __future__ import annotations

import logging

from app.services.evolink_api import (
    call_evolink_text,
    call_evolink_text_with_images,
    generate_image_evolink,
    is_evolink_configured,
)
from app.services.google_api import (
    call_google_gemini_api,
    call_google_gemini_api_with_images,
    generate_image_google,
    get_google_api_key,
    is_quota_error,
)

logger = logging.getLogger("app.ai_api")


def _is_gemini_file_error(exc: Exception) -> bool:
    """Gemini Files API 上传/处理失败（与 quota 无关，但可以 fallback 到 Evolink 重试）。"""
    msg = str(exc)
    return "Gemini file processing failed" in msg or "Gemini file processing timeout" in msg


def _should_fallback(exc: Exception) -> bool:
    """fallback 触发条件：(Google quota 耗尽 OR Gemini 文件处理失败) AND Evolink 已配置。

    Evolink Native API（v1beta/generateContent）与 Google 原生协议同构，
    text / image / video / audio / pdf 都支持，所以不再因 video 输入跳过。
    """
    if not (is_quota_error(exc) or _is_gemini_file_error(exc)):
        return False
    if not is_evolink_configured():
        logger.warning("ai_api: Google error but EVOLINK_API_KEY 未配置，跳过 fallback")
        return False
    return True


async def call_gemini_api(
    *,
    model_name: str,
    prompt: str,
    temperature: float = 0.3,
    video_url: str | None = None,
    response_schema: dict | None = None,
    timeout: float = 120.0,
) -> str:
    """文本（可带视频）生成。"""
    google_key = get_google_api_key()
    if not google_key:
        raise ValueError("AI API 未配置：请在 .env 中设置 GOOGLE_API_KEY。")

    logger.debug("ai_api: calling Google SDK (model=%s)", model_name)
    try:
        return await call_google_gemini_api(
            api_key=google_key,
            model_name=model_name,
            prompt=prompt,
            temperature=temperature,
            video_url=video_url,
            response_schema=response_schema,
            timeout=timeout,
        )
    except Exception as exc:
        if not _should_fallback(exc):
            raise
        reason = "文件处理失败" if _is_gemini_file_error(exc) else "quota 耗尽"
        logger.warning(
            "ai_api: Google %s，fallback → Evolink (model_name=%s, has_video=%s, prompt_chars=%d)",
            reason, model_name, bool(video_url), len(prompt or ""),
        )
        return await call_evolink_text(
            prompt=prompt,
            video_url=video_url,
            temperature=temperature,
            response_schema=response_schema,
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
    """文本 + 多图参考。"""
    google_key = get_google_api_key()
    if not google_key:
        raise ValueError("AI API 未配置：请在 .env 中设置 GOOGLE_API_KEY。")

    logger.debug("ai_api: calling Google SDK with images (model=%s, refs=%d)", model_name, len(image_urls or []))
    try:
        return await call_google_gemini_api_with_images(
            api_key=google_key,
            model_name=model_name,
            prompt=prompt,
            image_urls=image_urls,
            temperature=temperature,
            response_schema=response_schema,
            timeout=timeout,
        )
    except Exception as exc:
        if not _should_fallback(exc):
            raise
        logger.warning(
            "ai_api: Google quota 耗尽，fallback → Evolink (with_images, model_name=%s, refs=%d)",
            model_name, len(image_urls or []),
        )
        return await call_evolink_text_with_images(
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
    """图像生成。返回 image bytes。"""
    google_key = get_google_api_key()
    if not google_key:
        raise ValueError("AI API 未配置：请在 .env 中设置 GOOGLE_API_KEY。")

    logger.debug("ai_api: image gen via Google SDK (model=%s)", model_name)
    try:
        return await generate_image_google(
            api_key=google_key,
            model_name=model_name,
            prompt=prompt,
            image_urls=image_urls,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
            temperature=temperature,
        )
    except Exception as exc:
        if not _should_fallback(exc):
            raise
        logger.warning(
            "ai_api: Google quota 耗尽，fallback → Evolink generate_image (model_name=%s, refs=%d)",
            model_name, len(image_urls or []),
        )
        return await generate_image_evolink(
            prompt=prompt,
            image_urls=image_urls,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        )
