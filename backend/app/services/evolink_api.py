"""Evolink AI 适配层（Google quota 耗尽后的 fallback vendor）。

文档：https://docs.evolink.ai/

- 文本 / 多模态（text + image + video + audio + pdf）：
  POST {EVOLINK_TEXT_BASE_URL}/v1beta/models/{model}:generateContent
  这是 Google Gemini 的 Native API 协议，与 ai_api 调用方语义一致。
  之前只在 OpenAI SDK 入口上 fallback 会丢失 video 输入能力，所以这里走 Native。
- 图像生成（nanobanana-pro，异步）：
  POST {EVOLINK_API_BASE_URL}/v1/images/generations → 返回 task_id
  GET  {EVOLINK_API_BASE_URL}/v1/tasks/{task_id}     → 轮询结果

约束（文档摘录）：
  image: image/jpeg|png，单图 ≤ 10MB
  video: video/mp4，单文件 ≤ 50MB，建议 ≤ 180s
  audio: audio/mp3，≤ 10MB
  pdf:   application/pdf，≤ 20MB
"""
from __future__ import annotations

import asyncio
import logging
import mimetypes
from urllib.parse import urlparse

import httpx

from app.core.config import settings

logger = logging.getLogger("app.evolink_api")


def get_evolink_api_key() -> str:
    return settings.evolink_api_key


def is_evolink_configured() -> bool:
    return bool(settings.evolink_api_key)


def _auth_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.evolink_api_key}",
        "Content-Type": "application/json",
    }


# ── Native API 工具：构造 contents[].parts[] ───────────────────────────────────

_IMAGE_EXT_TO_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

_VIDEO_EXT_TO_MIME = {
    ".mp4": "video/mp4",
    ".mov": "video/mp4",  # mov 也走 mp4 mime（Gemini Native 主要识别 video/mp4）
}


def _ext_of(url: str) -> str:
    path = urlparse(url).path
    idx = path.rfind(".")
    return path[idx:].lower() if idx >= 0 else ""


def _guess_image_mime(url: str) -> str:
    ext = _ext_of(url)
    return _IMAGE_EXT_TO_MIME.get(ext, "image/jpeg")


def _guess_video_mime(url: str) -> str:
    ext = _ext_of(url)
    return _VIDEO_EXT_TO_MIME.get(ext, "video/mp4")


def _build_parts(
    prompt: str,
    *,
    image_urls: list[str] | None = None,
    video_url: str | None = None,
) -> list[dict]:
    parts: list[dict] = [{"text": prompt}]
    if video_url:
        parts.append({
            "fileData": {
                "mimeType": _guess_video_mime(video_url),
                "fileUri": video_url,
            }
        })
    if image_urls:
        for u in image_urls:
            if not u:
                continue
            parts.append({
                "fileData": {
                    "mimeType": _guess_image_mime(u),
                    "fileUri": u,
                }
            })
    return parts


def _build_generation_config(
    temperature: float,
    response_schema: dict | None,
) -> dict:
    cfg: dict = {"temperature": float(temperature)}
    if response_schema is not None:
        # Native API 对应字段；OpenAI 的 response_format 不在这条线上
        cfg["responseMimeType"] = "application/json"
        cfg["responseSchema"] = response_schema
    return cfg


def _extract_text(data: dict) -> str:
    """从 Native API 响应里拼出 text 内容。"""
    try:
        candidates = data["candidates"]
        parts = candidates[0]["content"]["parts"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Evolink 返回结构异常: {data}") from exc
    chunks: list[str] = []
    for p in parts:
        if isinstance(p, dict) and "text" in p:
            chunks.append(str(p["text"]))
    return "".join(chunks)


# ── 公共：文本 / 多模态 ─────────────────────────────────────────────────────────

async def call_evolink_text(
    *,
    prompt: str,
    model: str | None = None,
    temperature: float = 0.3,
    video_url: str | None = None,
    image_urls: list[str] | None = None,
    response_schema: dict | None = None,
    timeout: float = 180.0,
) -> str:
    """文本生成；支持 video + 多张图片混合输入。返回拼接后的文本。"""
    if not is_evolink_configured():
        raise RuntimeError("Evolink 未配置：请在 .env 中设置 EVOLINK_API_KEY")

    model_name = model or settings.evolink_text_model
    url = (
        f"{settings.evolink_text_base_url.rstrip('/')}"
        f"/v1beta/models/{model_name}:generateContent"
    )
    payload = {
        "contents": [{"role": "user", "parts": _build_parts(
            prompt, image_urls=image_urls, video_url=video_url,
        )}],
        "generationConfig": _build_generation_config(temperature, response_schema),
    }
    logger.info(
        "evolink_api: POST %s has_video=%s images=%d schema=%s",
        url, bool(video_url), len(image_urls or []), bool(response_schema),
    )
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, headers=_auth_headers(), json=payload)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Evolink generateContent {resp.status_code}: {resp.text[:500]}"
            )
        return _extract_text(resp.json())


async def call_evolink_text_with_images(
    *,
    prompt: str,
    image_urls: list[str],
    model: str | None = None,
    temperature: float = 0.3,
    response_schema: dict | None = None,
    timeout: float = 180.0,
) -> str:
    """带多张参考图的文本生成（call_evolink_text 的便捷别名）。"""
    return await call_evolink_text(
        prompt=prompt,
        model=model,
        temperature=temperature,
        image_urls=image_urls,
        response_schema=response_schema,
        timeout=timeout,
    )


# ── 图像生成（异步任务 → 轮询 → 下载） ──────────────────────────────────────────

# Google generate_image 的 aspect_ratio 取值 → Evolink size 字段
_ASPECT_TO_SIZE = {
    "1:1": "1:1", "9:16": "9:16", "16:9": "16:9",
    "2:3": "2:3", "3:2": "3:2", "3:4": "3:4", "4:3": "4:3",
    "4:5": "4:5", "5:4": "5:4", "21:9": "21:9",
}

# Google image_size 取值 → Evolink quality
_SIZE_TO_QUALITY = {"1K": "1K", "2K": "2K", "4K": "4K"}


def _map_aspect_to_size(aspect_ratio: str) -> str:
    return _ASPECT_TO_SIZE.get(aspect_ratio, "auto")


def _map_size_to_quality(image_size: str) -> str:
    return _SIZE_TO_QUALITY.get(image_size, "2K")


async def _submit_evolink_image_task(
    *,
    prompt: str,
    image_urls: list[str] | None,
    size: str,
    quality: str,
    model: str | None,
    timeout: float,
) -> str:
    """提交图像生成任务，返回 task_id。"""
    url = f"{settings.evolink_api_base_url.rstrip('/')}/v1/images/generations"
    payload: dict = {
        "model": model or settings.evolink_image_model,
        "prompt": prompt,
        "size": size,
        "quality": quality,
    }
    if image_urls:
        payload["image_urls"] = [u for u in image_urls if u]

    logger.info(
        "evolink_api: POST %s model=%s size=%s quality=%s refs=%d",
        url, payload["model"], size, quality, len(payload.get("image_urls") or []),
    )
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, headers=_auth_headers(), json=payload)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Evolink images/generations {resp.status_code}: {resp.text[:500]}"
            )
        data = resp.json()
    task_id = data.get("id")
    if not task_id:
        raise RuntimeError(f"Evolink 提交后未返回 task id: {data}")
    return str(task_id)


async def _fetch_evolink_task(task_id: str, timeout: float) -> dict:
    url = f"{settings.evolink_api_base_url.rstrip('/')}/v1/tasks/{task_id}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url, headers=_auth_headers())
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Evolink tasks/{task_id} {resp.status_code}: {resp.text[:500]}"
            )
        return resp.json()


async def _download_image_bytes(url: str, timeout: float) -> bytes:
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


async def generate_image_evolink(
    *,
    prompt: str,
    image_urls: list[str] | None = None,
    aspect_ratio: str = "9:16",
    image_size: str = "1K",
    model: str | None = None,
) -> bytes:
    """异步任务提交 → 轮询 → 下载首张图片为 bytes。"""
    if not is_evolink_configured():
        raise RuntimeError("Evolink 未配置：请在 .env 中设置 EVOLINK_API_KEY")

    size = _map_aspect_to_size(aspect_ratio)
    quality = _map_size_to_quality(image_size)

    task_id = await _submit_evolink_image_task(
        prompt=prompt,
        image_urls=image_urls,
        size=size,
        quality=quality,
        model=model,
        timeout=60.0,
    )
    logger.info("evolink_api: image task submitted task_id=%s", task_id)

    deadline = asyncio.get_event_loop().time() + settings.evolink_image_poll_timeout_sec
    interval = settings.evolink_image_poll_interval_sec
    while True:
        await asyncio.sleep(interval)
        data = await _fetch_evolink_task(task_id, timeout=30.0)
        status = data.get("status")
        progress = data.get("progress")
        logger.debug("evolink_api: task_id=%s status=%s progress=%s", task_id, status, progress)

        if status == "completed":
            results = data.get("results") or []
            if not results:
                raise RuntimeError(f"Evolink 任务完成但 results 为空: {data}")
            return await _download_image_bytes(str(results[0]), timeout=60.0)
        if status == "failed":
            err = data.get("error") or {}
            raise RuntimeError(
                f"Evolink 图像生成失败: code={err.get('code')} message={err.get('message')}"
            )
        if asyncio.get_event_loop().time() >= deadline:
            raise RuntimeError(
                f"Evolink 任务 {task_id} 轮询超时（status={status}, progress={progress}）"
            )
