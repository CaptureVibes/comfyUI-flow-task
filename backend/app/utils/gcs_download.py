"""GCS 视频下载工具：把 `gs://bucket/path/x.mp4` 拉到本地临时文件。

vendor 把视频上传到自己的 GCS bucket（`gs://decom-objects/...`），
我们通过 google-cloud-storage SDK + GOOGLE_APPLICATION_CREDENTIALS 凭证下载。

同时提供 `download_url_to_local` 作为统一下载入口：传入任意 URL，
若是 GCS（`gs://` 或 `https://storage.googleapis.com/...`）就走 SDK
（服务账号凭证，可访问私有桶），其余走 httpx 流式下载。
"""
from __future__ import annotations

import asyncio
import logging
import os
from urllib.parse import unquote, urlparse

logger = logging.getLogger("app.gcs_download")

_GCS_HTTPS_HOSTS = ("storage.googleapis.com", "storage.cloud.google.com")


def parse_gs_uri(uri: str) -> tuple[str, str]:
    """`gs://bucket/key/path.mp4` → (bucket, key)。"""
    if not uri.startswith("gs://"):
        raise ValueError(f"Not a gs:// URI: {uri}")
    parsed = urlparse(uri)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    if not bucket or not key:
        raise ValueError(f"无效的 gs:// URI: {uri}")
    return bucket, key


def is_gcs_url(url: str) -> bool:
    """判断是否是 GCS 资源（gs:// 或 storage.googleapis.com 公网链接形式）。"""
    if url.startswith("gs://"):
        return True
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and parsed.netloc in _GCS_HTTPS_HOSTS


def parse_gcs_url(url: str) -> tuple[str, str]:
    """解析 gs:// 或 https://storage.googleapis.com/{bucket}/{key} 形式 → (bucket, key)。"""
    if url.startswith("gs://"):
        return parse_gs_uri(url)
    parsed = urlparse(url)
    if parsed.netloc not in _GCS_HTTPS_HOSTS:
        raise ValueError(f"not a GCS public URL: {url}")
    path = parsed.path.lstrip("/")
    parts = path.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"invalid GCS public URL: {url}")
    return parts[0], unquote(parts[1])


async def _download_blob_to_file(bucket_name: str, key: str, out_path: str) -> None:
    """SDK 下载（同步调用包到线程池）。失败抛异常。"""

    def _run_sync() -> None:
        from google.cloud import storage  # type: ignore

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(key)
        logger.info("gcs_download: gs://%s/%s -> %s", bucket_name, key, out_path)
        blob.download_to_filename(out_path)

    await asyncio.to_thread(_run_sync)
    if not os.path.exists(out_path):
        raise RuntimeError(f"GCS 下载完成但文件不存在: {out_path}")


async def download_gs_to_local(gs_uri: str, out_path: str) -> str:
    """下载 gs:// 文件到本地 out_path（如不以 .mp4 结尾则自动追加）。

    返回实际写入的本地文件路径。失败抛异常。
    """
    file_path = out_path if out_path.endswith(".mp4") else out_path + ".mp4"
    bucket_name, key = parse_gs_uri(gs_uri)
    await _download_blob_to_file(bucket_name, key, file_path)
    return file_path


async def _httpx_stream_to_file(
    url: str,
    out_path: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float,
) -> int:
    """httpx 流式下载到 out_path，返回字节数。"""
    import httpx

    total = 0
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(timeout, connect=30.0),
        follow_redirects=True,
        headers=headers,
        trust_env=False,
    ) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            with open(out_path, "wb") as f:
                async for chunk in resp.aiter_bytes(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    f.write(chunk)
                    total += len(chunk)
    return total


async def download_url_to_local(
    url: str,
    out_path: str,
    *,
    http_headers: dict[str, str] | None = None,
    timeout: float = 600.0,
) -> int:
    """统一下载入口：

    - `gs://...` 或 `https://storage.googleapis.com/...` → google-cloud-storage SDK
      （服务账号凭证，可访问私有桶）
    - 其它 URL → httpx 流式下载

    返回写入的字节数。失败抛异常。
    """
    if is_gcs_url(url):
        bucket, key = parse_gcs_url(url)
        await _download_blob_to_file(bucket, key, out_path)
        return os.path.getsize(out_path)
    return await _httpx_stream_to_file(url, out_path, headers=http_headers, timeout=timeout)
