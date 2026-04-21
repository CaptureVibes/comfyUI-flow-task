"""
backfill_publish_meta_pending.py
=================================
将所有 status=queued 且 publish_meta IS NULL 且有 result_video_url 的子任务
批量写入 publish_meta={"status":"pending"} 并加入 AI 标题生成队列。

用法（在服务器 backend/ 目录下）：
    uv run python scripts/backfill_publish_meta_pending.py [--dry-run]

--dry-run: 只打印数量，不写入数据库、不入队
"""
from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

sys.path.insert(0, ".")


async def main(dry_run: bool = False) -> None:
    from app.db.session import SessionLocal
    from app.models.video_task import VideoSubTask

    async with SessionLocal() as session:
        rows = (await session.execute(
            select(VideoSubTask).where(
                VideoSubTask.status == "queued",
                VideoSubTask.publish_meta.is_(None),
                VideoSubTask.result_video_url.isnot(None),
            )
        )).scalars().all()

    print(f"找到 {len(rows)} 条需要补填的子任务")

    if dry_run or not rows:
        print("dry-run 模式，不执行写入。")
        return

    # 批量写 pending
    async with SessionLocal() as session:
        ids = [r.id for r in rows]
        subs = (await session.execute(
            select(VideoSubTask).where(VideoSubTask.id.in_(ids))
        )).scalars().all()
        for sub in subs:
            sub.publish_meta = {"status": "pending"}
        await session.commit()
    print(f"已将 {len(subs)} 条记录写入 publish_meta=pending")

    # 启动 worker 并入队
    from app.services.publish_meta_service import (
        start_publish_meta_workers,
        enqueue_publish_meta_task,
        stop_publish_meta_workers,
    )

    await start_publish_meta_workers()
    for sub in subs:
        enqueue_publish_meta_task(sub.id)
    print(f"已将 {len(subs)} 条任务加入生成队列，等待处理完成…")

    # 等待队列清空
    from app.services.publish_meta_service import _task_deque
    while _task_deque:
        await asyncio.sleep(2)

    # 额外等10秒让最后一批 worker 写回 DB
    await asyncio.sleep(10)
    await stop_publish_meta_workers()
    print("全部完成。")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(main(dry_run=dry_run))
