"""
迁移脚本：修复 accounts 和 video_tasks 中图片 URL 的错误扩展名（.png → .jpg）

背景：之前上传图片时 content_type 硬编码为 image/png，导致实际为 JPEG 的图片
以 .png 扩展名存储到 CDN。本脚本通过下载文件头（只取前 12 字节）检测实际格式，
若检测为 JPEG 则将 URL 中的 .png 后缀改为 .jpg。

用法：
    cd backend
    uv run python scripts/fix_image_extensions.py [--dry-run]

选项：
    --dry-run   只打印变更，不写入数据库
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from sqlalchemy import select, update

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("fix_image_ext")

DRY_RUN = "--dry-run" in sys.argv

# 只取前 12 字节判断魔数，省流量
_HEAD_BYTES = 12
_SEMAPHORE = asyncio.Semaphore(20)  # 最大并发下载数


def _is_jpeg(data: bytes) -> bool:
    return data[:3] == b"\xff\xd8\xff"


def _fix_url(url: str) -> str | None:
    """将错误扩展名统一为 .jpg：
    - .png → 下载验证魔数后决定是否改
    - .jpeg → 直接改为 .jpg（同格式，无需验证）
    返回修正后的 URL，若不需要修改则返回 None。
    """
    if not url:
        return None
    lower = url.lower()
    if lower.endswith(".jpeg"):
        return url[:-5] + ".jpg"
    if lower.endswith(".png"):
        return url[:-4] + ".jpg"   # 仍需魔数验证，在调用方处理
    return None


async def _fetch_head(client: httpx.AsyncClient, url: str) -> bytes:
    async with _SEMAPHORE:
        try:
            async with client.stream("GET", url, timeout=15.0) as resp:
                resp.raise_for_status()
                data = b""
                async for chunk in resp.aiter_bytes(chunk_size=_HEAD_BYTES):
                    data += chunk
                    if len(data) >= _HEAD_BYTES:
                        break
                return data
        except Exception as exc:
            logger.warning("下载头部失败 %s: %s", url[:80], exc)
            return b""


async def _check_and_fix_url(client: httpx.AsyncClient, url: str) -> str | None:
    """返回修正后的 URL，若不需要修改或无法判断则返回 None。"""
    candidate = _fix_url(url)
    if candidate is None:
        return None  # 不是 .png，跳过
    head = await _fetch_head(client, url)
    if not head:
        return None
    if _is_jpeg(head):
        return candidate
    return None  # 虽然扩展名 .png 但确实是 PNG，不改


# ---------------------------------------------------------------------------
# accounts 表
# ---------------------------------------------------------------------------

async def fix_accounts(session, client: httpx.AsyncClient) -> int:
    from app.models.account import Account

    rows = (await session.execute(select(Account))).scalars().all()
    changed = 0

    async def _fix_one(acc: Account) -> None:
        nonlocal changed
        fields = {"avatar_url", "photo_url", "painting_url"}
        updates: dict[str, str] = {}
        tasks = {
            f: asyncio.create_task(_check_and_fix_url(client, getattr(acc, f) or ""))
            for f in fields
            if getattr(acc, f)
        }
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for field, result in zip(tasks.keys(), results):
            if isinstance(result, str) and result:
                updates[field] = result

        if updates:
            log_parts = [f"{k}: {getattr(acc, k)[:60]} → {v[:60]}" for k, v in updates.items()]
            logger.info("Account %s: %s", acc.id, " | ".join(log_parts))
            if not DRY_RUN:
                for k, v in updates.items():
                    setattr(acc, k, v)
            changed += 1

    await asyncio.gather(*[_fix_one(acc) for acc in rows])

    if not DRY_RUN and changed:
        await session.commit()

    return changed


# ---------------------------------------------------------------------------
# video_tasks 表（shots JSON）
# ---------------------------------------------------------------------------

async def fix_video_tasks(session, client: httpx.AsyncClient) -> int:
    from app.models.video_task import VideoTask

    rows = (await session.execute(
        select(VideoTask).where(VideoTask.shots.isnot(None))
    )).scalars().all()
    changed = 0

    async def _fix_task(task: VideoTask) -> None:
        nonlocal changed
        shots: list[dict[str, Any]] = task.shots or []
        if not shots:
            return

        # 并发检测所有 shot 的 image_url
        indices_to_check = [
            i for i, s in enumerate(shots)
            if isinstance(s.get("image_url"), str) and s["image_url"].lower().endswith(".png")
        ]
        if not indices_to_check:
            return

        results = await asyncio.gather(*[
            _check_and_fix_url(client, shots[i]["image_url"])
            for i in indices_to_check
        ])

        new_shots = [s.copy() for s in shots]
        task_changed = False
        for idx, new_url in zip(indices_to_check, results):
            if new_url:
                logger.info("VideoTask %s shot[%d]: %s → %s",
                            task.id, idx, shots[idx]["image_url"][:60], new_url[:60])
                new_shots[idx]["image_url"] = new_url
                task_changed = True

        if task_changed:
            if not DRY_RUN:
                task.shots = new_shots
            changed += 1

    await asyncio.gather(*[_fix_task(t) for t in rows])

    if not DRY_RUN and changed:
        await session.commit()

    return changed


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

async def main() -> None:
    from app.db.session import SessionLocal

    if DRY_RUN:
        logger.info("=== DRY RUN 模式，不写入数据库 ===")

    async with httpx.AsyncClient(follow_redirects=True) as client:
        async with SessionLocal() as session:
            logger.info("--- 处理 accounts 表 ---")
            acc_changed = await fix_accounts(session, client)
            logger.info("accounts 完成：%d 条记录需要修正", acc_changed)

            logger.info("--- 处理 video_tasks.shots ---")
            task_changed = await fix_video_tasks(session, client)
            logger.info("video_tasks 完成：%d 个任务需要修正", task_changed)

    logger.info("全部完成。%s", "（DRY RUN，未实际写入）" if DRY_RUN else "已写入数据库。")


if __name__ == "__main__":
    asyncio.run(main())
