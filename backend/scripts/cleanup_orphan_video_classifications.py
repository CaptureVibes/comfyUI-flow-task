"""
清理脚本：删除 video_classifications 中 video_source_id 已不存在于
video_sources 的孤儿记录。

背景：早前的清理脚本删除了部分 video_sources，但 video_classifications
没有联动删除，导致博主分类聚合（accounts.classification_summary）的 total
膨胀。

用法：
    cd backend
    uv run python scripts/cleanup_orphan_video_classifications.py --dry-run
    uv run python scripts/cleanup_orphan_video_classifications.py
"""
from __future__ import annotations

import argparse
import asyncio
import sys

sys.path.insert(0, ".")

from sqlalchemy import delete, func, select

from app.db.session import SessionLocal
from app.models.video_classification import VideoClassification
from app.models.video_source import VideoSource


async def run(dry_run: bool) -> None:
    async with SessionLocal() as session:
        total_stmt = select(func.count()).select_from(VideoClassification)
        total = (await session.execute(total_stmt)).scalar() or 0

        orphan_select = (
            select(VideoClassification.id)
            .outerjoin(VideoSource, VideoSource.id == VideoClassification.video_source_id)
            .where(VideoSource.id.is_(None))
        )
        orphan_ids = [row[0] for row in (await session.execute(orphan_select)).fetchall()]
        print(f"[video_classifications] 总计 {total} 条，孤儿 {len(orphan_ids)} 条")

        if not orphan_ids:
            print("无需清理。")
            return

        if dry_run:
            preview = orphan_ids[:10]
            print(f"=== DRY RUN ===  示例 ID（前 {len(preview)} 个）:")
            for cid in preview:
                print(f"  - {cid}")
            return

        result = await session.execute(
            delete(VideoClassification).where(VideoClassification.id.in_(orphan_ids))
        )
        await session.commit()
        print(f"已删除 video_classifications: {result.rowcount} 条")


def main() -> None:
    parser = argparse.ArgumentParser(description="清理 video_classifications 孤儿记录")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不执行删除")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
