"""
重新计算所有 AI 博主的分类聚合结果。

视频已分类完毕，只需按账号重跑 _recompute_account_summary。

用法：
    cd backend
    uv run python scripts/recompute_account_classification_summary.py

可选过滤（只处理指定 owner）：
    uv run python scripts/recompute_account_classification_summary.py --owner-id <uuid>
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid

sys.path.insert(0, ".")  # 确保 app 包可以被 import

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.account import Account
from app.models.account_blogger_binding import AccountBloggerBinding
from app.models.video_classification import VideoClassification
from app.models.video_source import VideoSource
from app.services.video_classification_service import _recompute_account_summary


async def _fetch_account_ids(owner_id: uuid.UUID | None) -> list[uuid.UUID]:
    """查找所有有视频分类记录的账号 ID。"""
    async with SessionLocal() as session:
        stmt = (
            select(AccountBloggerBinding.account_id)
            .join(VideoSource, VideoSource.tiktok_blogger_id == AccountBloggerBinding.tiktok_blogger_id)
            .join(VideoClassification, VideoClassification.video_source_id == VideoSource.id)
            .distinct()
        )
        if owner_id is not None:
            stmt = stmt.join(Account, Account.id == AccountBloggerBinding.account_id).where(
                Account.owner_id == owner_id
            )
        rows = (await session.scalars(stmt)).all()
    return list(rows)


async def main(owner_id: uuid.UUID | None) -> None:
    account_ids = await _fetch_account_ids(owner_id)
    if not account_ids:
        print("没有找到需要重算的账号")
        return

    print(f"共 {len(account_ids)} 个账号需要重算")
    for i, aid in enumerate(account_ids, 1):
        try:
            await _recompute_account_summary(aid)
            print(f"[{i}/{len(account_ids)}] {aid} ✓")
        except Exception as exc:
            print(f"[{i}/{len(account_ids)}] {aid} ✗ {exc}")

    print("完成")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner-id", default=None, help="只处理指定 owner 的账号")
    args = parser.parse_args()

    owner_uuid: uuid.UUID | None = None
    if args.owner_id:
        try:
            owner_uuid = uuid.UUID(args.owner_id)
        except ValueError:
            print(f"--owner-id 格式无效: {args.owner_id}")
            sys.exit(1)

    asyncio.run(main(owner_uuid))
