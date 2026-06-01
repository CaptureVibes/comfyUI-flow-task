"""
清洗历史分类数据：将所有 video_classifications 记录重置为 pending，
同时清空 category_key / category_index / major_category / classified_at，
并将关联账号的 classification_type / classification_summary 清空。

用法：
    cd backend
    uv run python scripts/reset_classifications.py

可选参数：
    --owner-id <uuid>   只处理指定 owner 的数据
    --dry-run           只打印数量，不实际修改
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid

sys.path.insert(0, ".")

from sqlalchemy import select, update

from app.db.session import SessionLocal
from app.models.account import Account
from app.models.account_blogger_binding import AccountBloggerBinding
from app.models.video_classification import VideoClassification
from app.models.video_source import VideoSource


async def main(owner_id: uuid.UUID | None, dry_run: bool) -> None:
    async with SessionLocal() as session:
        # 找出所有需要重置的 classification 行
        stmt = select(VideoClassification.id, VideoClassification.video_source_id)
        if owner_id is not None:
            stmt = stmt.where(VideoClassification.owner_id == owner_id)
        rows = (await session.execute(stmt)).all()

        if not rows:
            print("没有找到 video_classifications 记录")
            return

        ids = [r.id for r in rows]
        print(f"共 {len(ids)} 条分类记录{'（dry-run，不实际修改）' if dry_run else '，将全部重置为 pending'}")

        if dry_run:
            return

        # 批量重置分类行
        await session.execute(
            update(VideoClassification)
            .where(VideoClassification.id.in_(ids))
            .values(
                status="pending",
                category_key=None,
                category_index=None,
                major_category=None,
                error_message=None,
                classified_at=None,
            )
        )

        # 找出关联账号，清空聚合结果
        vs_ids = [r.video_source_id for r in rows]
        blogger_ids_rows = (await session.execute(
            select(VideoSource.tiktok_blogger_id)
            .where(VideoSource.id.in_(vs_ids))
            .where(VideoSource.tiktok_blogger_id.isnot(None))
            .distinct()
        )).scalars().all()

        if blogger_ids_rows:
            account_ids = (await session.scalars(
                select(AccountBloggerBinding.account_id)
                .where(AccountBloggerBinding.tiktok_blogger_id.in_(list(blogger_ids_rows)))
                .distinct()
            )).all()

            if account_ids:
                await session.execute(
                    update(Account)
                    .where(Account.id.in_(list(account_ids)))
                    .values(
                        classification_type=None,
                        classification_summary=None,
                        classification_status="idle",
                    )
                )
                print(f"已清空 {len(account_ids)} 个账号的分类聚合")

        await session.commit()
        print("重置完成。请运行 alembic upgrade head 后重新触发分类。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner-id", default=None, help="只处理指定 owner 的数据")
    parser.add_argument("--dry-run", action="store_true", help="只统计数量，不修改数据库")
    args = parser.parse_args()

    owner_uuid: uuid.UUID | None = None
    if args.owner_id:
        try:
            owner_uuid = uuid.UUID(args.owner_id)
        except ValueError:
            print(f"--owner-id 格式无效: {args.owner_id}")
            sys.exit(1)

    asyncio.run(main(owner_uuid, args.dry_run))
