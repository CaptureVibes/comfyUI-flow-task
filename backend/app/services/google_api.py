"""Google Gemini SDK client (google-genai) — text generation + image generation."""
from __future__ import annotations

import asyncio
import base64
import logging
import mimetypes
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx
from google import genai
from google.genai import types

logger = logging.getLogger("app.google_api")

_QUOTA_RETRY_DELAY_SECONDS = 30
_QUOTA_MAX_RETRIES = 15

_MEDIA_DOWNLOAD_HEADERS = {
    "Accept": "*/*",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
}


@dataclass(frozen=True)
class _DownloadedMedia:
    path: Path
    filename: str
    mime_type: str
    size: int


def get_google_api_key() -> str:
    """Return GOOGLE_API_KEY from settings (loaded from .env), or empty string if not set."""
    from app.core.config import settings
    return settings.google_api_key


def _make_client(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key)


def _is_quota_error(exc: Exception) -> bool:
    exc_str = str(exc)
    return (
        "429" in exc_str
        or "RESOURCE_EXHAUSTED" in exc_str
        or "Too Many Requests" in exc_str
    )


def _retry_delay_seconds(exc: Exception, attempt: int) -> int:
    if _is_quota_error(exc):
        return _QUOTA_RETRY_DELAY_SECONDS
    return min(attempt * 2, 30)


def _should_retry_error(exc: Exception, failed_attempt: int, default_max_attempts: int) -> bool:
    if _is_quota_error(exc):
        return failed_attempt <= _QUOTA_MAX_RETRIES
    return failed_attempt < default_max_attempts


def _retry_limit_label(exc: Exception, default_max_attempts: int) -> str:
    if _is_quota_error(exc):
        return str(_QUOTA_MAX_RETRIES)
    return str(default_max_attempts)


def _max_loop_attempts(default_max_attempts: int) -> int:
    return max(default_max_attempts, _QUOTA_MAX_RETRIES + 1)


async def _run_with_quota_retries(operation: str, call):
    retry_count = 0
    while True:
        try:
            return await call()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not _is_quota_error(exc) or retry_count >= _QUOTA_MAX_RETRIES:
                raise
            retry_count += 1
            logger.warning(
                "%s got quota error, retry %d/%d in %ds: %s",
                operation,
                retry_count,
                _QUOTA_MAX_RETRIES,
                _QUOTA_RETRY_DELAY_SECONDS,
                exc,
            )
            await asyncio.sleep(_QUOTA_RETRY_DELAY_SECONDS)


def _is_bad_request_error(exc: Exception) -> bool:
    exc_str = str(exc)
    return "400" in exc_str or "Cannot fetch content" in exc_str


def _file_state_name(file: object) -> str:
    state = getattr(file, "state", None)
    return getattr(state, "name", None) or getattr(state, "value", None) or str(state)


def _filename_from_url(url: str, fallback_extension: str) -> str:
    filename = Path(urlparse(url).path).name
    if filename:
        return filename
    return f"gemini-media-{uuid.uuid4().hex}{fallback_extension}"


def _normalize_mime_type(content_type: str | None, filename: str, fallback: str) -> str:
    raw = (content_type or "").split(";", 1)[0].strip().lower()
    if raw.startswith(("image/", "video/")):
        return raw
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or fallback


async def _download_media_to_temp_file(
    url: str,
    *,
    fallback_mime_type: str,
    timeout: float,
) -> _DownloadedMedia:
    fallback_extension = mimetypes.guess_extension(fallback_mime_type) or ".bin"
    filename = _filename_from_url(url, fallback_extension)
    suffix = Path(filename).suffix or fallback_extension

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = Path(tmp.name)

    total = 0
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=30.0),
            follow_redirects=True,
            headers=_MEDIA_DOWNLOAD_HEADERS,
            trust_env=False,
        ) as client:
            async with client.stream("GET", url) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    preview = body[:500].decode("utf-8", errors="ignore")
                    raise RuntimeError(
                        f"download media failed: status={response.status_code}, "
                        f"url={response.url}, body={preview}"
                    )

                mime_type = _normalize_mime_type(
                    response.headers.get("content-type"),
                    filename,
                    fallback_mime_type,
                )
                with tmp_path.open("wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        f.write(chunk)
                        total += len(chunk)

        return _DownloadedMedia(
            path=tmp_path,
            filename=filename,
            mime_type=mime_type,
            size=total,
        )
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            logger.warning("Failed to clean temp media file: %s", tmp_path)
        raise


async def _wait_gemini_file_active(client: genai.Client, file_name: str):
    for _ in range(60):
        file = await _run_with_quota_retries(
            "Gemini Files get",
            lambda: client.aio.files.get(name=file_name),
        )
        state = _file_state_name(file)
        if state == "ACTIVE":
            return file
        if state == "FAILED":
            raise RuntimeError(f"Gemini file processing failed: {file}")
        await asyncio.sleep(2)
    raise RuntimeError(f"Gemini file processing timeout: {file_name}")


async def _upload_url_to_gemini_file(
    client: genai.Client,
    url: str,
    *,
    fallback_mime_type: str,
    timeout: float,
):
    media = await _download_media_to_temp_file(
        url,
        fallback_mime_type=fallback_mime_type,
        timeout=timeout,
    )
    try:
        logger.info(
            "Uploading media fallback to Gemini Files: url=%s size=%d mime=%s",
            url[:160],
            media.size,
            media.mime_type,
        )
        file = await _run_with_quota_retries(
            "Gemini Files upload",
            lambda: client.aio.files.upload(
                file=media.path,
                config=types.UploadFileConfig(
                    mimeType=media.mime_type,
                    displayName=media.filename,
                ),
            ),
        )
        if getattr(file, "name", None):
            file = await _wait_gemini_file_active(client, file.name)
        return file
    finally:
        try:
            media.path.unlink(missing_ok=True)
        except Exception:
            logger.warning("Failed to clean temp media file: %s", media.path)


async def _delete_gemini_files(client: genai.Client, files: list[object]) -> None:
    for file in files:
        name = getattr(file, "name", None)
        if not name:
            continue
        try:
            await client.aio.files.delete(name=name)
        except Exception as exc:
            logger.warning("Failed to delete Gemini fallback file %s: %s", name, exc)


async def _generate_content_with_uploaded_media(
    client: genai.Client,
    *,
    model_name: str,
    prompt: str,
    media_urls: list[tuple[str, str, str | None]],
    config: types.GenerateContentConfig,
    timeout: float,
    require_text: bool,
) -> str:
    uploaded_files: list[object] = []
    parts: list[types.Part] = []
    try:
        for url, fallback_mime_type, label in media_urls:
            if label:
                parts.append(types.Part.from_text(text=label))
            file = await _upload_url_to_gemini_file(
                client,
                url,
                fallback_mime_type=fallback_mime_type,
                timeout=timeout,
            )
            uploaded_files.append(file)
            file_uri = getattr(file, "uri", None)
            file_mime_type = getattr(file, "mime_type", None) or fallback_mime_type
            if not file_uri:
                raise RuntimeError(f"Gemini uploaded file has no uri: {file}")
            parts.append(types.Part.from_uri(file_uri=file_uri, mime_type=file_mime_type))

        parts.append(types.Part.from_text(text=prompt))
        response = await _run_with_quota_retries(
            "Google SDK media fallback generate_content",
            lambda: client.aio.models.generate_content(
                model=model_name,
                contents=[types.Content(role="user", parts=parts)],
                config=config,
            ),
        )
        text = response.text or ""
        logger.info("Google SDK media fallback response: %s", text[:500])
        if require_text and not text:
            raise ValueError(f"模型 {model_name} 返回空响应")
        return text
    finally:
        await _delete_gemini_files(client, uploaded_files)


def _extract_image_bytes(response: object) -> bytes | None:
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in (getattr(content, "parts", None) or []):
            inline_data = getattr(part, "inline_data", None)
            data = getattr(inline_data, "data", None) if inline_data else None
            if not data:
                continue
            if isinstance(data, (bytes, bytearray)):
                return bytes(data)
            return base64.b64decode(data)
    return None


async def _generate_image_with_uploaded_media(
    client: genai.Client,
    *,
    model_name: str,
    prompt: str,
    image_urls: list[str],
    config: types.GenerateContentConfig,
    timeout: float,
) -> bytes:
    uploaded_files: list[object] = []
    parts: list[types.Part] = []
    try:
        for i, url in enumerate(image_urls):
            parts.append(types.Part.from_text(text=f"参考图{i + 1}"))
            file = await _upload_url_to_gemini_file(
                client,
                url,
                fallback_mime_type="image/jpeg",
                timeout=timeout,
            )
            uploaded_files.append(file)
            file_uri = getattr(file, "uri", None)
            file_mime_type = getattr(file, "mime_type", None) or "image/jpeg"
            if not file_uri:
                raise RuntimeError(f"Gemini uploaded file has no uri: {file}")
            parts.append(types.Part.from_uri(file_uri=file_uri, mime_type=file_mime_type))

        parts.append(types.Part.from_text(text=prompt))
        response = await _run_with_quota_retries(
            "Google SDK image fallback generate_content",
            lambda: client.aio.models.generate_content(
                model=model_name,
                contents=[types.Content(role="user", parts=parts)],
                config=config,
            ),
        )
        image_bytes = _extract_image_bytes(response)
        if image_bytes is not None:
            logger.info("Google SDK image gen fallback success: %d bytes", len(image_bytes))
            return image_bytes
        raise ValueError(f"Google SDK image gen fallback: no image in response — {response}")
    finally:
        await _delete_gemini_files(client, uploaded_files)


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
    while attempt < _max_loop_attempts(max_attempts):
        attempt += 1
        try:
            response = await client.aio.models.generate_content(
                model=model_name,
                contents=[types.Content(role="user", parts=parts)],
                config=config,
            )
            text = response.text
            logger.info("Google SDK text response: %s", (text or "")[:500])
            if not text:
                raise ValueError(f"模型 {model_name} 返回空响应")
            return text

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # 4xx 不重试（配置错误）
            exc_str = str(exc)
            if video_url and _is_bad_request_error(exc):
                logger.warning(
                    "Google SDK text got 400, fallback to Gemini Files immediately: "
                    "model=%s video=%s error=%s",
                    model_name,
                    video_url[:160],
                    exc,
                )
                return await _generate_content_with_uploaded_media(
                    client,
                    model_name=model_name,
                    prompt=prompt,
                    media_urls=[(video_url, "video/mp4", None)],
                    config=config,
                    timeout=timeout,
                    require_text=True,
                )
            if any(code in exc_str for code in ["400", "401", "403", "404"]):
                logger.error(
                    "Google SDK 4xx error (不重试): model=%s video=%s prompt=%s\n%s",
                    model_name, video_url, prompt[:300], exc,
                )
                raise
            if not _should_retry_error(exc, attempt, max_attempts):
                logger.error("Google SDK text 已达最大重试次数 %s，放弃: model=%s %s", _retry_limit_label(exc, max_attempts), model_name, exc)
                raise
            delay = _retry_delay_seconds(exc, attempt)
            logger.warning("Google SDK text attempt %d/%s failed (%ds后重试): %s", attempt, _retry_limit_label(exc, max_attempts), delay, exc)
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
    while attempt < _max_loop_attempts(max_attempts):
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
            if image_urls and _is_bad_request_error(exc):
                logger.warning(
                    "Google SDK text+images got 400, fallback to Gemini Files immediately: "
                    "model=%s images=%d error=%s",
                    model_name,
                    len(image_urls),
                    exc,
                )
                fallback_media = [
                    (url, "image/jpeg", f"参考图{i + 1}")
                    for i, url in enumerate(image_urls)
                ]
                return await _generate_content_with_uploaded_media(
                    client,
                    model_name=model_name,
                    prompt=prompt,
                    media_urls=fallback_media,
                    config=config,
                    timeout=timeout,
                    require_text=False,
                )
            if any(code in exc_str for code in ["400", "401", "403", "404"]):
                logger.error("Google SDK 4xx error (不重试): model=%s %s", model_name, exc)
                raise
            if not _should_retry_error(exc, attempt, max_attempts):
                logger.error("Google SDK text+images 已达最大重试次数 %s，放弃: %s", _retry_limit_label(exc, max_attempts), exc)
                raise
            delay = _retry_delay_seconds(exc, attempt)
            logger.warning("Google SDK text+images attempt %d/%s failed (%ds后重试): %s", attempt, _retry_limit_label(exc, max_attempts), delay, exc)
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
    while attempt < _max_loop_attempts(max_attempts):
        attempt += 1
        try:
            response = await client.aio.models.generate_content(
                model=model_name,
                contents=[types.Content(role="user", parts=parts)],
                config=config,
            )

            # 从响应中提取图片 bytes
            image_bytes = _extract_image_bytes(response)
            if image_bytes is not None:
                logger.info("Google SDK image gen success: %d bytes", len(image_bytes))
                return image_bytes

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
            if image_urls and _is_bad_request_error(exc):
                logger.warning(
                    "Google SDK image gen got 400, fallback to Gemini Files immediately: "
                    "model=%s images=%d error=%s",
                    model_name,
                    len(image_urls),
                    exc,
                )
                return await _generate_image_with_uploaded_media(
                    client,
                    model_name=model_name,
                    prompt=prompt,
                    image_urls=image_urls,
                    config=config,
                    timeout=180.0,
                )
            if any(code in exc_str for code in ["400", "401", "403", "404"]):
                logger.error("Google SDK image gen 4xx (不重试): %s", exc)
                raise
            if "blocked by safety filter" in exc_str:
                raise
            if not _should_retry_error(exc, attempt, max_attempts):
                logger.error("Google SDK image gen 已达最大重试次数 %s，放弃: %s", _retry_limit_label(exc, max_attempts), exc)
                raise
            delay = _retry_delay_seconds(exc, attempt)
            logger.warning("Google SDK image gen attempt %d/%s failed (%ds后重试): %s", attempt, _retry_limit_label(exc, max_attempts), delay, exc)
            await asyncio.sleep(delay)
