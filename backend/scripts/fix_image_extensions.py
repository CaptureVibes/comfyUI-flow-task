"""
迁移脚本：修复 accounts 和 video_tasks 中图片 URL 的错误扩展名

背景：之前上传图片时 content_type 硬编码为 image/png，导致实际为 JPEG 的图片
以 .png / .jpeg 扩展名存储到 CDN。

修复流程（每张图片）：
  1. URL 扩展名为 .png / .jpeg 才处理，其他跳过
  2. 完整下载原图
  3. 检测魔数确认实际格式
  4. 用正确扩展名重新上传到 CDN
  5. 用新 CDN URL 更新数据库

用法：
    cd backend
    uv run python scripts/fix_image_extensions.py [--dry-run]

选项：
    --dry-run   只打印变更，不写入数据库（仍会下载+上传以验证可行性）
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from sqlalchemy import select

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("fix_image_ext")

DRY_RUN = "--dry-run" in sys.argv
_SEMAPHORE = asyncio.Semaphore(5)  # 并发限制（下载+上传都占用）


def _needs_fix(url: str) -> bool:
    """只处理扩展名为 .png 或 .jpeg 的 URL。"""
    if not url:
        return False
    lower = url.lower()
    return lower.endswith(".png") or lower.endswith(".jpeg")


def _detect_content_type(data: bytes) -> tuple[str, str] | None:
    """检测图片格式，返回 (content_type, extension)，无法识别返回 None。"""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg", ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png", ".png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif", ".gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", ".webp"
    return None


def _base_filename(url: str) -> str:
    """从 URL 取文件名（去掉扩展名）。"""
    name = url.rstrip("/").split("/")[-1].split("?")[0]
    base, _ = os.path.splitext(name)
    return base or "image"


async def _download_and_reupload(client: httpx.AsyncClient, url: str) -> str | None:
    """
    下载 url，检测实际格式，若扩展名有误则重新上传到 CDN，返回新 URL。
    若格式已正确或出错则返回 None。
    """
    async with _SEMAPHORE:
        # 1. 下载完整图片
        try:
            resp = await client.get(url, timeout=60.0)
            resp.raise_for_status()
            data = resp.content
        except Exception as exc:
            logger.warning("下载失败 %s: %s", url[:80], exc)
            return None

        # 2. 检测格式
        detected = _detect_content_type(data)
        if detected is None:
            logger.warning("无法识别格式 %s，跳过", url[:80])
            return None

        content_type, correct_ext = detected
        current_lower = url.lower()

        # 3. 判断是否需要修正
        already_correct = current_lower.endswith(correct_ext)
        if already_correct:
            logger.debug("格式已正确 %s，跳过", url[:80])
            return None

        # 4. 重新上传
        filename = _base_filename(url) + correct_ext
        if DRY_RUN:
            logger.info("[DRY RUN] 需重传 %s → %s (格式: %s)", url[:80], filename, content_type)
            return f"<would_upload:{filename}>"

        try:
            from app.services.upload_service import UpstreamImageUploadService
            svc = UpstreamImageUploadService()
            result = await svc.upload_image(data, content_type, filename)
            logger.info("重传完成 %s → %s", url[:80], result.url[:80])
            return result.url
        except Exception as exc:
            logger.error("上传失败 %s: %s", url[:80], exc)
            return None


# ---------------------------------------------------------------------------
# accounts 表
# ---------------------------------------------------------------------------

async def fix_accounts(session, client: httpx.AsyncClient) -> int:
    from app.models.account import Account

    rows = (await session.execute(select(Account))).scalars().all()
    # 只处理有需要修复的字段的账号
    candidates = [
        acc for acc in rows
        if any(_needs_fix(getattr(acc, f) or "") for f in ("avatar_url", "photo_url"))
    ]
    logger.info("accounts: 共 %d 条，需检查 %d 条", len(rows), len(candidates))

    changed = 0

    async def _fix_one(acc: Account) -> None:
        nonlocal changed
        fields = [f for f in ("avatar_url", "photo_url") if _needs_fix(getattr(acc, f) or "")]
        tasks = {f: asyncio.create_task(_download_and_reupload(client, getattr(acc, f))) for f in fields}
        results = {f: await t for f, t in tasks.items()}

        any_changes = {f: url for f, url in results.items() if url}
        updates = {f: url for f, url in any_changes.items() if not url.startswith("<would_upload")}
        if any_changes:
            if not DRY_RUN and updates:
                for k, v in updates.items():
                    setattr(acc, k, v)
            display = updates if updates else any_changes
            log_parts = [f"{k}: ...{getattr(acc, k)[-40:]} → ...{v[-40:]}" for k, v in display.items()]
            logger.info("Account %s 更新: %s", acc.id, " | ".join(log_parts))
            changed += 1

    await asyncio.gather(*[_fix_one(acc) for acc in candidates])

    if not DRY_RUN and changed:
        await session.commit()
        logger.info("accounts: 已 commit %d 条变更", changed)

    return changed


# ---------------------------------------------------------------------------
# video_tasks 表（shots JSON）
# ---------------------------------------------------------------------------

async def fix_video_tasks(session, client: httpx.AsyncClient) -> int:
    from app.models.video_task import VideoTask

    rows = (await session.execute(
        select(VideoTask).where(VideoTask.shots.isnot(None))
    )).scalars().all()

    candidates = [
        t for t in rows
        if any(_needs_fix(s.get("image_url", "")) for s in (t.shots or []))
    ]
    logger.info("video_tasks: 共 %d 条有 shots，需检查 %d 条", len(rows), len(candidates))

    changed = 0

    async def _fix_task(task: VideoTask) -> None:
        nonlocal changed
        shots: list[dict[str, Any]] = task.shots or []
        indices = [i for i, s in enumerate(shots) if _needs_fix(s.get("image_url", ""))]

        results = await asyncio.gather(*[
            _download_and_reupload(client, shots[i]["image_url"])
            for i in indices
        ])

        new_shots = [s.copy() for s in shots]
        task_changed = False
        for i, new_url in zip(indices, results):
            if new_url and not new_url.startswith("<would_upload"):
                new_shots[i]["image_url"] = new_url
                task_changed = True
            elif new_url:  # dry run placeholder
                task_changed = True

        if task_changed:
            if not DRY_RUN:
                task.shots = new_shots
            changed += 1

    await asyncio.gather(*[_fix_task(t) for t in candidates])

    if not DRY_RUN and changed:
        await session.commit()
        logger.info("video_tasks: 已 commit %d 条变更", changed)

    return changed


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

async def main() -> None:
    from app.db.session import SessionLocal

    if DRY_RUN:
        logger.info("=== DRY RUN 模式（下载+检测，但不写入数据库）===")

    async with httpx.AsyncClient(follow_redirects=True) as client:
        async with SessionLocal() as session:
            logger.info("--- 处理 accounts 表 ---")
            acc_changed = await fix_accounts(session, client)
            logger.info("accounts 完成：%d 条记录已修正", acc_changed)

            logger.info("--- 处理 video_tasks.shots ---")
            task_changed = await fix_video_tasks(session, client)
            logger.info("video_tasks 完成：%d 个任务已修正", task_changed)

    suffix = "（DRY RUN，未写入数据库）" if DRY_RUN else "已写入数据库。"
    logger.info(
        "=== 汇总 %s: accounts 需修正 %d 条，video_tasks 需修正 %d 个任务 ===",
        suffix, acc_changed, task_changed,
    )


if __name__ == "__main__":
    asyncio.run(main())
