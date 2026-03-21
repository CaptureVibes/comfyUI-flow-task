"""
修复脚本：根据子任务状态重新计算所有父任务状态

用法：
    cd backend
    uv run python scripts/fix_task_statuses.py

逻辑：复用 _compute_parent_status 的优先级规则，
对每个 video_task 根据其 sub_tasks 的状态集合重新算出正确状态。
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import SessionLocal
from app.models.video_task import VideoSubTask, VideoTask


def compute_parent_status(sub_tasks: list[VideoSubTask]) -> str:
    if any(st.selected and st.status == "published" for st in sub_tasks):
        return "published"
    statuses = {st.status for st in sub_tasks if st.status != "abandoned"}
    if not statuses:
        return "abandoned"
    if "publishing" in statuses:
        return "publishing"
    if "publish_failed" in statuses:
        return "publish_failed"
    if "queued" in statuses:
        return "queued"
    if "pending_publish" in statuses:
        return "pending_publish"
    if "reviewing" in statuses:
        return "reviewing"
    if "scoring" in statuses:
        return "scoring"
    if "generating" in statuses:
        return "generating"
    return "pending"


async def main():
    async with SessionLocal() as session:
        tasks = (
            await session.execute(
                select(VideoTask).options(selectinload(VideoTask.sub_tasks))
            )
        ).scalars().all()

        fixed = 0
        for task in tasks:
            correct = compute_parent_status(task.sub_tasks)
            if task.status != correct:
                sub_statuses = [st.status for st in task.sub_tasks]
                print(f"[FIX] Task {task.id}  {task.status} -> {correct}  (subs: {sub_statuses})")
                task.status = correct
                fixed += 1

        if fixed:
            await session.commit()
            print(f"\nDone. Fixed {fixed} task(s).")
        else:
            print("All task statuses are already correct. Nothing to fix.")


if __name__ == "__main__":
    asyncio.run(main())
