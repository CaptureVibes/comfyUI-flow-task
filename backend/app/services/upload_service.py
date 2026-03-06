from __future__ import annotations

import base64
import binascii
import mimetypes
import uuid
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

        extension = mimetypes.guess_extension(content_type) or ".png"
        safe_name = filename or f"upload-{uuid.uuid4().hex}{extension}"

        last_exc: Exception | None = None
        response = None
        for attempt in range(1, 4):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        settings.upload_api_url,
                        files={"file": (safe_name, content, content_type)},
                        headers={"Accept": "*/*"},
                    )
                last_exc = None
                break
            except httpx.RequestError as exc:
                last_exc = exc
                if attempt < 3:
                    import asyncio
                    await asyncio.sleep(attempt)

        if last_exc is not None:
            raise UpstreamError(f"Upload upstream request failed after 3 attempts: {last_exc}") from last_exc

        if response.status_code >= 400:
            raise UpstreamError(f"Upload upstream returned {response.status_code}: {response.text[:300]}")

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
