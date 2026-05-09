"""
回填 video_sub_tasks 的 status / selected 字段，与已存在的 video_publications 对齐。

历史 bug：batch_route_stashed 漏设 selected=True；同时 _apply_publication_status_to_sub_task
有状态守卫，sub_task 不在 (queued/pending_publish/publish_failed/publishing) 时静默跳过 →
导致已经成功发布（video_publications 存在 completed/partial/failed 行）的 sub_task
status 还停在 stashed/abandoned/...，selected 还是 False。

本脚本扫描所有有 publication 的 sub_task，按 publication 的最新状态对齐：
  publication.status ∈ ("completed", "partial") → sub_task.status = "published", selected=True
  publication.status == "failed"                → sub_task.status = "publish_failed", selected=True
  其余（pending/processing/uploading）            → sub_task.status = "publishing",   selected=True

同一 sub_task 多条 publication 时，按 created_at desc 取最新一条。

用法：
    cd backend

    # 预览（只统计，不改 DB）
    uv run python scripts/backfill_sub_task_status_from_publications.py --dry-run

    # 实际回填
    uv run python scripts/backfill_sub_task_status_from_publications.py

    # 只跑某一个 sub_task
    uv run python scripts/backfill_sub_task_status_from_publications.py --sub-task-id <uuid>
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models.video_publication import VideoPublication  # noqa: E402
from app.models.video_task import VideoSubTask, VideoTask  # noqa: E402
from app.services.video_task_service import _compute_parent_status  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scripts.backfill_sub_task_status_from_publications")


_PUB_TO_SUB_STATUS = {
    "completed": "published",
    "partial": "published",
    "failed": "publish_failed",
    "pending": "publishing",
    "processing": "publishing",
    "uploading": "publishing",
}


async def _run(*, dry_run: bool, only_sub_task_id: uuid.UUID | None) -> None:
    async with SessionLocal() as session:
        # 取每个 sub_task 的最新一条 publication
        stmt = (
            select(VideoPublication)
            .order_by(VideoPublication.sub_task_id, VideoPublication.created_at.desc())
        )
        if only_sub_task_id is not None:
            stmt = stmt.where(VideoPublication.sub_task_id == only_sub_task_id)
        pubs = list((await session.execute(stmt)).scalars().all())

    latest_by_sub: dict[uuid.UUID, VideoPublication] = {}
    for pub in pubs:
        if pub.sub_task_id not in latest_by_sub:
            latest_by_sub[pub.sub_task_id] = pub
    logger.info("待评估 sub_task 数（有 publication）: %d", len(latest_by_sub))

    counts = {"already_ok": 0, "fixed_sub": 0, "fixed_parent": 0,
              "skipped_unknown_status": 0, "missing_sub_task": 0}
    fixed_log: list[str] = []
    affected_task_ids: set = set()

    async with SessionLocal() as session:
        for sub_id, pub in latest_by_sub.items():
            target_status = _PUB_TO_SUB_STATUS.get(pub.status or "")
            if target_status is None:
                counts["skipped_unknown_status"] += 1
                continue
            sub = await session.scalar(select(VideoSubTask).where(VideoSubTask.id == sub_id))
            if sub is None:
                counts["missing_sub_task"] += 1
                continue
            need_status = sub.status != target_status
            need_selected = not sub.selected
            if not need_status and not need_selected:
                counts["already_ok"] += 1
                continue

            line = (
                f"  sub={sub_id} pub_status={pub.status} "
                f"sub_status={sub.status}→{target_status if need_status else sub.status} "
                f"selected={sub.selected}→{'True' if need_selected else sub.selected}"
            )
            fixed_log.append(line)
            counts["fixed_sub"] += 1
            affected_task_ids.add(sub.task_id)

            if not dry_run:
                if need_status:
                    sub.status = target_status
                if need_selected:
                    sub.selected = True

        # 重算被影响 task 的 parent.status
        for task_id in affected_task_ids:
            task = await session.scalar(
                select(VideoTask)
                .where(VideoTask.id == task_id)
                .options(selectinload(VideoTask.sub_tasks))
            )
            if task is None:
                continue
            new_status = _compute_parent_status(task.sub_tasks)
            if task.status != new_status:
                fixed_log.append(
                    f"  task={task_id} status={task.status}→{new_status}"
                )
                counts["fixed_parent"] += 1
                if not dry_run:
                    task.status = new_status

        if not dry_run and (counts["fixed_sub"] > 0 or counts["fixed_parent"] > 0):
            await session.commit()

    logger.info("=" * 72)
    if dry_run:
        logger.info("[DRY-RUN] 将修复 sub %d 条 + parent %d 条：",
                    counts["fixed_sub"], counts["fixed_parent"])
    else:
        logger.info("已修复 sub %d 条 + parent %d 条：",
                    counts["fixed_sub"], counts["fixed_parent"])
    for line in fixed_log[:200]:
        logger.info(line)
    if len(fixed_log) > 200:
        logger.info("... 省略 %d 条", len(fixed_log) - 200)
    logger.info(
        "汇总：fixed_sub=%d, fixed_parent=%d, already_ok=%d, "
        "skipped_unknown_status=%d, missing_sub_task=%d",
        counts["fixed_sub"], counts["fixed_parent"], counts["already_ok"],
        counts["skipped_unknown_status"], counts["missing_sub_task"],
    )
    logger.info("=" * 72)


async def main() -> None:
    parser = argparse.ArgumentParser(description="按 video_publications 状态回填 video_sub_tasks.status / selected")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不修改 DB")
    parser.add_argument("--sub-task-id", type=str, default=None, help="只处理指定 sub_task")
    args = parser.parse_args()

    only = uuid.UUID(args.sub_task_id) if args.sub_task_id else None
    await _run(dry_run=args.dry_run, only_sub_task_id=only)


if __name__ == "__main__":
    asyncio.run(main())
