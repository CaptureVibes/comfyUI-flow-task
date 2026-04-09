from __future__ import annotations

import base64
import binascii
import mimetypes
import uuid
import asyncio
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.core.exceptions import UpstreamError, ValidationError


@dataclass
class UploadResult:
    url: str
    object_key: str
    content_type: str
    size: int


def ensure_image_constraints(content: bytes, content_type: str) -> None:
    if not content:
        raise ValidationError("Image cannot be empty")
    if len(content) > settings.max_image_size_bytes:
        raise ValidationError(f"Image too large. Max size is {settings.max_image_size_mb}MB")
    if not content_type.startswith("image/"):
        raise ValidationError("Only image content is allowed")


def detect_image_content_type(data: bytes) -> tuple[str, str]:
    """通过魔数检测图片格式，返回 (content_type, extension)。"""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg", ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png", ".png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif", ".gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", ".webp"
    return "image/jpeg", ".jpg"


def decode_base64_image(data: str) -> tuple[bytes, str]:
    content_type = "image/png"
    raw_data = data

    if data.startswith("data:") and ";base64," in data:
        header, raw_data = data.split(";base64,", 1)
        content_type = header.replace("data:", "").strip() or "image/png"

    try:
        decoded = base64.b64decode(raw_data, validate=True)
    except binascii.Error as exc:
        raise ValidationError("Invalid base64 image") from exc

    # 如果没有 data URI 头，用魔数检测实际格式
    if not data.startswith("data:"):
        content_type, _ = detect_image_content_type(decoded)

    return decoded, content_type


def _find_first_str(payload: object, keys: set[str]) -> str | None:
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        for value in payload.values():
            found = _find_first_str(value, keys)
            if found:
                return found
    if isinstance(payload, list):
        for item in payload:
            found = _find_first_str(item, keys)
            if found:
                return found
    return None


class UpstreamImageUploadService:
    async def upload_image(self, content: bytes, content_type: str, filename: str | None = None) -> UploadResult:
        ensure_image_constraints(content, content_type)

        _EXT_MAP = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/gif": ".gif",
            "image/bmp": ".bmp",
        }
        extension = _EXT_MAP.get(content_type) or mimetypes.guess_extension(content_type) or ".jpg"
        safe_name = filename or f"upload-{uuid.uuid4().hex}{extension}"

        response = None
        attempt = 0
        while True:
            attempt += 1
            try:
                async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
                    response = await client.post(
                        settings.upload_api_url,
                        files={"file": (safe_name, content, content_type)},
                        headers={"Accept": "*/*"},
                    )
                if response.status_code >= 400:
                    raise UpstreamError(f"Upload upstream returned {response.status_code}: {response.text[:300]}")
                break
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                delay = min(attempt * 2, 30)
                import logging as _logging
                _logging.getLogger("app.upload_service").warning(
                    "upload_image attempt %d failed (%ds后重试): %s", attempt, delay, exc
                )
                await asyncio.sleep(delay)

        try:
            payload = response.json()
        except ValueError as exc:
            raise UpstreamError("Upload upstream did not return JSON") from exc

        url = _find_first_str(payload, {"url", "image_url", "file_url", "data", "src"})
        if not url:
            raise UpstreamError("Upload upstream JSON does not contain image url")

        object_key = _find_first_str(payload, {"object_key", "key", "path"})
        if not object_key:
            parsed = urlparse(url)
            object_key = parsed.path.lstrip("/") or safe_name

        return UploadResult(
            url=url,
            object_key=object_key,
            content_type=content_type,
            size=len(content),
        )
