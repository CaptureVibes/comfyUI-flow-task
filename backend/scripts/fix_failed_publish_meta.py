"""
修复 publish_meta.status == "failed" 的子任务：
用 task.prompt 前 100 字作为 title，直接写入 done 状态。

用法：
    uv run python scripts/fix_failed_publish_meta.py
    uv run python scripts/fix_failed_publish_meta.py --dry-run        # 只打印不写入
    uv run python scripts/fix_failed_publish_meta.py --owner-id <uuid>  # 只修复指定 owner
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

# 把 backend 目录加入 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import SessionLocal
from app.models.video_task import VideoSubTask, VideoTask


async def fix_failed_publish_meta(
    *,
    dry_run: bool = False,
    owner_id: uuid.UUID | None = None,
) -> None:
    async with SessionLocal() as session:
        stmt = (
            select(VideoSubTask)
            .join(VideoTask, VideoSubTask.task_id == VideoTask.id)
            .where(
                VideoSubTask.publish_meta["status"].as_string() == "failed",
            )
            .options(selectinload(VideoSubTask.task))
        )
        if owner_id is not None:
            stmt = stmt.where(VideoTask.owner_id == owner_id)

        rows = (await session.execute(stmt)).scalars().all()

    print(f"找到 {len(rows)} 条 publish_meta=failed 的子任务")
    if not rows:
        return

    fixed = 0
    async with SessionLocal() as session:
        for sub in rows:
            task_prompt = (sub.task.prompt or "").strip()
            title = task_prompt[:100] if task_prompt else "How do you like this?"
            new_meta = {
                "status": "done",
                "title": title,
                "description": "",
                "hashtags": [],
            }
            # 保留原有 promotion_code / product_code_mode 等字段
            existing = sub.publish_meta if isinstance(sub.publish_meta, dict) else {}
            for key in ("promotion_code", "product_code_mode", "ext_products_count"):
                if key in existing:
                    new_meta[key] = existing[key]

            print(f"  [{'DRY' if dry_run else 'FIX'}] sub_task={sub.id}  title={title!r:.60}")
            if not dry_run:
                # 重新在当前 session 里获取并更新
                sub_obj = await session.get(VideoSubTask, sub.id)
                if sub_obj is not None:
                    sub_obj.publish_meta = new_meta
                    fixed += 1

        if not dry_run:
            await session.commit()

    print(f"\n完成：fixed={fixed}  dry_run={dry_run}")


def main() -> None:
    parser = argparse.ArgumentParser(description="修复 publish_meta=failed 的子任务")
    parser.add_argument("--dry-run", action="store_true", help="只打印不写入")
    parser.add_argument("--owner-id", type=str, default=None, help="只修复指定 owner 的数据")
    args = parser.parse_args()

    owner_id = uuid.UUID(args.owner_id) if args.owner_id else None
    asyncio.run(fix_failed_publish_meta(dry_run=args.dry_run, owner_id=owner_id))


if __name__ == "__main__":
    main()
