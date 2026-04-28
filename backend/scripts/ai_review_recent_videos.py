"""
对视频库「本周新增」（7天内 created_at）的视频重新 AI 审核。
审核不通过：删除关联的 VideoAITemplate，再删除 VideoSource。

用法：
    cd backend
    uv run python scripts/ai_review_recent_videos.py

可选参数：
    --owner-id <uuid>   只处理指定 owner 的视频
    --days <n>          覆盖"本周"天数（默认 7）
    --dry-run           只打印判断结果，不实际删除
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, ".")

from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models.video_ai_template import VideoAITemplate
from app.models.video_source import VideoSource
from app.services.candidate_service import _SearchConfig, _ai_review_single
from app.services.pipeline_settings_service import get_or_create_pipeline_settings


async def _load_ai_cfg(owner_id: uuid.UUID | None) -> _SearchConfig:
    cfg_owner = owner_id or uuid.UUID(int=0)
    async with SessionLocal() as session:
        pipeline_cfg = await get_or_create_pipeline_settings(session, cfg_owner)
        return _SearchConfig(pipeline_cfg)


async def _fetch_recent_videos(
    owner_id: uuid.UUID | None,
    days: int,
) -> list[VideoSource]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    async with SessionLocal() as session:
        stmt = select(VideoSource).where(VideoSource.created_at >= since)
        if owner_id is not None:
            stmt = stmt.where(VideoSource.owner_id == owner_id)
        rows = (await session.scalars(stmt)).all()
        # detach from session so we can use outside
        return [VideoSource(**{c.key: getattr(r, c.key) for c in r.__table__.columns}) for r in rows]


async def _delete_video_and_templates(vs_id: uuid.UUID) -> None:
    async with SessionLocal() as session:
        await session.execute(
            delete(VideoAITemplate).where(VideoAITemplate.video_source_id == vs_id)
        )
        await session.execute(
            delete(VideoSource).where(VideoSource.id == vs_id)
        )
        await session.commit()


async def main(owner_id: uuid.UUID | None, days: int, dry_run: bool) -> None:
    cfg = await _load_ai_cfg(owner_id)

    if not cfg.ai_review_enabled:
        print("WARNING: candidate_ai_review_enabled=False，仍强制执行审核（脚本忽略开关）")
    if not cfg.ai_review_prompt:
        print("WARNING: AI 审核提示词为空，Gemini 将收到空 prompt")

    videos = await _fetch_recent_videos(owner_id, days)
    print(f"本周新增（{days}天内）共 {len(videos)} 条视频")

    passed = 0
    failed = 0
    skipped = 0
    deleted = 0

    for i, vs in enumerate(videos, 1):
        prefix = f"[{i}/{len(videos)}] {vs.id}"
        if not vs.local_video_url:
            print(f"{prefix} ⚠ 跳过（无 local_video_url）")
            skipped += 1
            continue

        try:
            prompt = (cfg.ai_review_prompt or "").replace("{keyword}", "")
            ok, reason = await _ai_review_single(
                video_url=vs.local_video_url,
                prompt=prompt,
                model=cfg.ai_review_model,
                retry_delay=cfg.retry_delay,
            )
        except Exception as exc:
            print(f"{prefix} ✗ 审核异常，跳过: {exc}")
            skipped += 1
            continue

        if ok:
            print(f"{prefix} ✓ 通过")
            passed += 1
        else:
            print(f"{prefix} ✗ 未通过 reason={reason!r}  title={vs.video_title!r}")
            failed += 1
            if dry_run:
                print(f"  [dry-run] 不删除")
            else:
                await _delete_video_and_templates(vs.id)
                deleted += 1
                print(f"  已删除 VideoSource + VideoAITemplate")

    print()
    print(f"完成：通过={passed}  未通过={failed}  跳过={skipped}  实际删除={deleted}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner-id", default=None)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    owner_uuid: uuid.UUID | None = None
    if args.owner_id:
        try:
            owner_uuid = uuid.UUID(args.owner_id)
        except ValueError:
            print(f"--owner-id 格式无效: {args.owner_id}")
            sys.exit(1)

    asyncio.run(main(owner_uuid, args.days, args.dry_run))
