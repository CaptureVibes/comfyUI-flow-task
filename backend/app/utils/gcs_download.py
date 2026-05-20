"""GCS 视频下载工具：把 `gs://bucket/path/x.mp4` 拉到本地临时文件。

vendor 把视频上传到自己的 GCS bucket（`gs://decom-objects/...`），
我们通过 google-cloud-storage SDK + GOOGLE_APPLICATION_CREDENTIALS 凭证下载。
"""
from __future__ import annotations

import asyncio
import logging
import os
from urllib.parse import urlparse

logger = logging.getLogger("app.gcs_download")


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


async def download_gs_to_local(gs_uri: str, out_path: str) -> str:
    """下载 gs:// 文件到本地 out_path（如不以 .mp4 结尾则自动追加）。

    返回实际写入的本地文件路径。失败抛异常。
    """
    file_path = out_path if out_path.endswith(".mp4") else out_path + ".mp4"
    bucket_name, key = parse_gs_uri(gs_uri)

    def _run_sync() -> None:
        from google.cloud import storage  # type: ignore

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(key)
        logger.info("gcs_download: gs://%s/%s -> %s", bucket_name, key, file_path)
        blob.download_to_filename(file_path)

    await asyncio.to_thread(_run_sync)
    if not os.path.exists(file_path):
        raise RuntimeError(f"GCS 下载完成但文件不存在: {file_path}")
    return file_path
