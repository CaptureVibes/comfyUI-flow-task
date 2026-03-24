"""
修复脚本：将 2026-03-24 日期、result_video_url 不为空的 abandoned 子任务恢复为 reviewing，
并重新计算对应父任务状态。

用法：
    cd backend
    uv run python scripts/fix_abandoned_20260324.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import SessionLocal
from app.models.video_task import VideoSubTask, VideoTask
from app.services.video_task_service import _compute_parent_status


async def main():
    async with SessionLocal() as db:
        # 查找 2026-03-24、有视频结果、状态为 abandoned 的子任务
        result = await db.execute(
            select(VideoSubTask)
            .join(VideoTask, VideoSubTask.task_id == VideoTask.id)
            .where(
                VideoTask.target_date == date(2026, 3, 24),
                VideoSubTask.status == "abandoned",
                VideoSubTask.result_video_url.isnot(None),
            )
            .options(selectinload(VideoSubTask.task).selectinload(VideoTask.sub_tasks))
        )
        sub_tasks = result.scalars().all()

        if not sub_tasks:
            print("No matching abandoned sub-tasks found.")
            return

        updated_task_ids = set()
        for sub in sub_tasks:
            print(f"  SubTask {sub.id}: {sub.status} -> reviewing")
            sub.status = "reviewing"
            updated_task_ids.add(sub.task_id)

        # 重新计算父任务状态
        for sub in sub_tasks:
            if sub.task_id in updated_task_ids:
                old_status = sub.task.status
                new_status = _compute_parent_status(sub.task.sub_tasks)
                if old_status != new_status:
                    print(f"  Task {sub.task_id}: {old_status} -> {new_status}")
                    sub.task.status = new_status
                updated_task_ids.discard(sub.task_id)

        await db.commit()
        print(f"\nDone. Updated {len(sub_tasks)} sub-task(s).")


if __name__ == "__main__":
    asyncio.run(main())
