"""Project-local 临时文件目录与磁盘空间预检。

部署机的 /tmp 默认是 tmpfs（RAM-backed）：抽帧 / 下载视频会迅速把 RAM 占满，
触发 OSError ENOSPC 让整条流水线失败。本模块统一让大文件落到 backend/.tmp/
（实际磁盘）下，并提供下载/抽帧前预检剩余空间的辅助函数。
"""
from __future__ import annotations

import logging
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)


# backend/app/utils/tmp_storage.py → parents[2] = backend/
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
TMP_DIR: Path = PROJECT_ROOT / ".tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)


def get_tmp_dir() -> str:
    """返回项目级临时目录的字符串路径，存在并可写。"""
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    return str(TMP_DIR)


def free_bytes() -> int:
    """返回 TMP_DIR 所在分区的剩余可用字节数。"""
    return shutil.disk_usage(get_tmp_dir()).free


def ensure_free_space(min_bytes: int = 500 * 1024 * 1024, *, label: str = "") -> None:
    """剩余磁盘空间小于 min_bytes 时立即抛错（fail-fast），避免重试浪费资源。"""
    free = free_bytes()
    if free < min_bytes:
        prefix = f"{label}: " if label else ""
        raise OSError(
            28,
            f"{prefix}临时目录可用空间不足（free={free / 1024 / 1024:.0f}MB,"
            f" required={min_bytes / 1024 / 1024:.0f}MB）；请清理 {get_tmp_dir()} 或所在分区。",
        )


@contextmanager
def disk_tempdir(prefix: str | None = None):
    """`tempfile.TemporaryDirectory` 包装：默认落到 backend/.tmp/ 下（实际磁盘）。"""
    base = get_tmp_dir()
    with tempfile.TemporaryDirectory(prefix=prefix, dir=base) as path:
        yield path


def disk_namedtempfile(*, suffix: str | None = None, prefix: str | None = None,
                       delete: bool = True):
    """`tempfile.NamedTemporaryFile` 包装：默认落到 backend/.tmp/ 下。"""
    return tempfile.NamedTemporaryFile(  # noqa: SIM115
        suffix=suffix, prefix=prefix, delete=delete, dir=get_tmp_dir()
    )


def cleanup_stale_tmp(*, max_age_seconds: int = 3600) -> int:
    """启动时清理 .tmp/ 下的残留：mtime 早于 max_age_seconds 的子项全删。

    进程被 kill -9 时 tempfile 的清理逻辑不会触发，会留下 orphan 目录/文件；
    定期清掉避免磁盘越占越大。返回清理的子项数量。
    """
    import os
    import time

    tmp_root = Path(get_tmp_dir())
    cutoff = time.time() - max_age_seconds
    removed = 0
    for child in tmp_root.iterdir():
        try:
            if child.stat().st_mtime >= cutoff:
                continue
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                os.unlink(child)
            removed += 1
        except Exception as exc:
            logger.warning("cleanup_stale_tmp: failed to remove %s: %s", child, exc)
    if removed:
        logger.info("cleanup_stale_tmp: removed %d stale entries from %s", removed, tmp_root)
    return removed
