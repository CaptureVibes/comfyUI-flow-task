"""
清理脚本：删除 2026-03-25 创建的原视频及其关联数据。

删除顺序：
1. video_source_tags（WHERE video_source_id IN ... OR video_ai_template_id IN ...）
2. video_ai_templates（WHERE video_source_id IN ...）
3. tags — 只删除已经没有任何 video_source_tags 关联的"孤儿"标签
4. video_sources（目标日期的记录）
5. candidate_videos.video_source_id SET NULL（数据库已有 ON DELETE SET NULL，删 video_sources 时自动触发）

用法：
    cd backend
    python -m scripts.cleanup_20260325 --dry-run   # 先预览
    python -m scripts.cleanup_20260325              # 真正执行
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone

from sqlalchemy import delete, func, select, text, update

# 确保 app 能被 import
sys.path.insert(0, ".")

from app.db.session import SessionLocal
from app.models.video_source import VideoSource
from app.models.video_ai_template import VideoAITemplate
from app.models.tag import Tag, VideoSourceTag


TARGET_DATE = datetime(2026, 3, 25, tzinfo=timezone.utc)
NEXT_DATE = datetime(2026, 3, 26, tzinfo=timezone.utc)


async def run(dry_run: bool) -> None:
    async with SessionLocal() as session:
        # 1. 查找目标 video_sources
        vs_ids_result = await session.execute(
            select(VideoSource.id).where(
                VideoSource.created_at >= TARGET_DATE,
                VideoSource.created_at < NEXT_DATE,
            )
        )
        vs_ids = [row[0] for row in vs_ids_result.fetchall()]
        print(f"[video_sources] 找到 {len(vs_ids)} 条 (2026-03-25)")

        if not vs_ids:
            print("没有需要清理的数据。")
            return

        # 2. 查找关联的 video_ai_templates
        tpl_ids_result = await session.execute(
            select(VideoAITemplate.id).where(
                VideoAITemplate.video_source_id.in_(vs_ids)
            )
        )
        tpl_ids = [row[0] for row in tpl_ids_result.fetchall()]
        print(f"[video_ai_templates] 找到 {len(tpl_ids)} 条关联模板")

        # 3. 查找关联的 tag_ids（通过 video_source_tags）
        tag_ids_result = await session.execute(
            select(VideoSourceTag.tag_id).where(
                (VideoSourceTag.video_source_id.in_(vs_ids))
                | (VideoSourceTag.video_ai_template_id.in_(tpl_ids) if tpl_ids else False)
            ).distinct()
        )
        tag_ids = [row[0] for row in tag_ids_result.fetchall()]
        print(f"[tags] 找到 {len(tag_ids)} 个关联标签（待检查是否为孤儿）")

        # 4. 统计 video_source_tags
        vst_count_result = await session.execute(
            select(func.count()).select_from(VideoSourceTag).where(
                (VideoSourceTag.video_source_id.in_(vs_ids))
                | (VideoSourceTag.video_ai_template_id.in_(tpl_ids) if tpl_ids else False)
            )
        )
        vst_count = vst_count_result.scalar()
        print(f"[video_source_tags] 找到 {vst_count} 条关联记录")

        if dry_run:
            print("\n=== DRY RUN 模式，不执行删除 ===")
            print(f"  将删除 video_source_tags: {vst_count} 条")
            print(f"  将删除 video_ai_templates: {len(tpl_ids)} 条")
            print(f"  将删除 video_sources: {len(vs_ids)} 条")
            print(f"  将检查并删除孤儿 tags: 最多 {len(tag_ids)} 个")
            return

        # ---- 执行删除 ----

        # Step A: 删除 video_source_tags
        del_vst = await session.execute(
            delete(VideoSourceTag).where(
                (VideoSourceTag.video_source_id.in_(vs_ids))
                | (VideoSourceTag.video_ai_template_id.in_(tpl_ids) if tpl_ids else False)
            )
        )
        print(f"  已删除 video_source_tags: {del_vst.rowcount} 条")

        # Step B: 删除 video_ai_templates
        if tpl_ids:
            del_tpl = await session.execute(
                delete(VideoAITemplate).where(VideoAITemplate.id.in_(tpl_ids))
            )
            print(f"  已删除 video_ai_templates: {del_tpl.rowcount} 条")

        # Step C: 删除 video_sources（cascade 会自动 SET NULL candidate_videos.video_source_id）
        del_vs = await session.execute(
            delete(VideoSource).where(VideoSource.id.in_(vs_ids))
        )
        print(f"  已删除 video_sources: {del_vs.rowcount} 条")

        # Step D: 删除孤儿标签（不再关联任何 video_source_tags 的标签）
        if tag_ids:
            orphan_result = await session.execute(
                select(Tag.id).where(
                    Tag.id.in_(tag_ids),
                    ~Tag.id.in_(
                        select(VideoSourceTag.tag_id).distinct()
                    ),
                )
            )
            orphan_ids = [row[0] for row in orphan_result.fetchall()]
            if orphan_ids:
                del_tags = await session.execute(
                    delete(Tag).where(Tag.id.in_(orphan_ids))
                )
                print(f"  已删除孤儿 tags: {del_tags.rowcount} 个")
            else:
                print("  无孤儿 tags 需要删除")

        await session.commit()
        print("\n清理完成。")


def main():
    parser = argparse.ArgumentParser(description="清理 2026-03-25 的视频及关联数据")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不执行删除")
    args = parser.parse_args()

    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
