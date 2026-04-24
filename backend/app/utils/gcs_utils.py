from __future__ import annotations

import asyncio
import logging
import mimetypes
import tempfile
import uuid
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote, urlparse

import httpx
from google.cloud import storage

from app.core.config import settings

logger = logging.getLogger("app.gcs_utils")


DEFAULT_VIDEO_DOWNLOAD_HEADERS = {
    "Accept": "*/*",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
}


@dataclass(frozen=True)
class DownloadedVideo:
    path: Path
    filename: str
    content_type: str
    size: int
    final_url: str


@dataclass(frozen=True)
class GCSUploadResult:
    bucket_name: str
    object_key: str
    gs_uri: str
    public_url: str
    content_type: str
    size: int


def _storage_client(project_id: str | None = None) -> storage.Client:
    return storage.Client(project=project_id or settings.gcs_project_id)


def _public_gcs_url(bucket_name: str, object_key: str) -> str:
    return f"https://storage.googleapis.com/{bucket_name}/{quote(object_key, safe='/')}"


def _filename_from_url(video_url: str) -> str:
    path_name = Path(urlparse(video_url).path).name
    if path_name and "." in path_name:
        return path_name
    return f"source-video-{uuid.uuid4().hex}.mp4"


def _default_object_key(filename: str, prefix: str = "debug/gemini-video-tests") -> str:
    suffix = Path(filename).suffix or ".mp4"
    return f"{prefix.strip('/')}/{uuid.uuid4().hex}{suffix}"


def _normalize_video_content_type(content_type: str | None, filename: str) -> str:
    raw = (content_type or "").split(";", 1)[0].strip().lower()
    if raw.startswith("video/"):
        return raw

    guessed, _ = mimetypes.guess_type(filename)
    if guessed and guessed.startswith("video/"):
        return guessed

    return "video/mp4"


async def download_video_to_temp_file(
    video_url: str,
    *,
    filename: str | None = None,
    timeout: float = 300.0,
    max_size_mb: int | None = None,
    headers: dict[str, str] | None = None,
) -> DownloadedVideo:
    source_filename = filename or _filename_from_url(video_url)
    suffix = Path(source_filename).suffix or ".mp4"
    max_size = max_size_mb * 1024 * 1024 if max_size_mb else None

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = Path(tmp.name)

    total = 0
    content_type = "video/mp4"
    final_url = video_url

    request_headers = dict(DEFAULT_VIDEO_DOWNLOAD_HEADERS)
    if headers:
        request_headers.update(headers)

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=30.0),
            follow_redirects=True,
            headers=request_headers,
            trust_env=False,
        ) as client:
            async with client.stream("GET", video_url) as response:
                final_url = str(response.url)
                content_type = _normalize_video_content_type(
                    response.headers.get("content-type"),
                    source_filename,
                )

                if response.status_code >= 400:
                    body = await response.aread()
                    preview = body[:1000].decode("utf-8", errors="ignore")
                    raise RuntimeError(
                        f"download failed: status={response.status_code}, "
                        f"url={final_url}, body={preview}"
                    )

                with tmp_path.open("wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        total += len(chunk)
                        if max_size and total > max_size:
                            raise RuntimeError(
                                f"downloaded video exceeds max_size_mb={max_size_mb}"
                            )
                        f.write(chunk)

        return DownloadedVideo(
            path=tmp_path,
            filename=source_filename,
            content_type=content_type,
            size=total,
            final_url=final_url,
        )
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            logger.warning("failed to clean temp video file: %s", tmp_path)
        raise


async def upload_video_file_to_gcs(
    file_path: str | Path,
    *,
    object_key: str | None = None,
    object_prefix: str = "debug/gemini-video-tests",
    bucket_name: str | None = None,
    project_id: str | None = None,
    content_type: str | None = None,
    cache_control: str | None = None,
) -> GCSUploadResult:
    path = Path(file_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"video file not found: {path}")

    bucket_name = bucket_name or settings.gcs_bucket_name
    object_key = object_key or _default_object_key(path.name, object_prefix)
    upload_content_type = _normalize_video_content_type(content_type, path.name)
    size = path.stat().st_size

    client = _storage_client(project_id)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_key)
    blob.chunk_size = 8 * 1024 * 1024
    if cache_control:
        blob.cache_control = cache_control

    await asyncio.to_thread(
        blob.upload_from_filename,
        str(path),
        content_type=upload_content_type,
    )

    logger.info(
        "uploaded video to GCS: gs://%s/%s size=%d content_type=%s",
        bucket_name,
        object_key,
        size,
        upload_content_type,
    )

    return GCSUploadResult(
        bucket_name=bucket_name,
        object_key=object_key,
        gs_uri=f"gs://{bucket_name}/{object_key}",
        public_url=_public_gcs_url(bucket_name, object_key),
        content_type=upload_content_type,
        size=size,
    )


async def upload_video_url_to_gcs(
    video_url: str,
    *,
    object_key: str | None = None,
    object_prefix: str = "debug/gemini-video-tests",
    bucket_name: str | None = None,
    project_id: str | None = None,
    timeout: float = 300.0,
    max_size_mb: int | None = None,
) -> GCSUploadResult:
    downloaded = await download_video_to_temp_file(
        video_url,
        timeout=timeout,
        max_size_mb=max_size_mb,
    )
    try:
        return await upload_video_file_to_gcs(
            downloaded.path,
            object_key=object_key or _default_object_key(downloaded.filename, object_prefix),
            object_prefix=object_prefix,
            bucket_name=bucket_name,
            project_id=project_id,
            content_type=downloaded.content_type,
        )
    finally:
        try:
            downloaded.path.unlink(missing_ok=True)
        except Exception:
            logger.warning("failed to clean temp video file: %s", downloaded.path)


async def upload_video_to_gcs(
    file_path: str | Path,
    **kwargs,
) -> GCSUploadResult:
    return await upload_video_file_to_gcs(file_path, **kwargs)


def generate_gcs_signed_url(
    *,
    bucket_name: str,
    object_key: str,
    project_id: str | None = None,
    expiration_minutes: int = 60,
) -> str:
    client = _storage_client(project_id)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_key)
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(minutes=expiration_minutes),
        method="GET",
    )
