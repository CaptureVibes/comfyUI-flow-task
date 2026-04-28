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
from app.models.candidate_video import CandidateVideo
from app.models.video_ai_template import VideoAITemplate
from app.models.video_source import VideoSource
from app.services.candidate_service import _SearchConfig
from app.services.pipeline_settings_service import get_or_create_pipeline_settings


async def _review_with_cdn_url(cdn_url: str, prompt: str, model: str) -> tuple[bool, str]:
    """直接用已在 CDN 上的 URL 调 Gemini 审核，跳过重新下载上传步骤。"""
    import json as _json
    from app.services.ai_api import call_gemini_api

    json_instructions = (
        "\n\n请必须以JSON格式输出审核结果，包含以下字段：\n"
        "- \"pass\": 布尔值（true 表示通过审核，false 表示不通过）\n"
        "- \"reason\": 字符串（简短说明原因，不超过50字）\n"
        "示例输出：\n"
        "{\"pass\": false, \"reason\": \"视频内容与关键词不相关\"}"
    )
    text = await call_gemini_api(
        model_name=model,
        video_url=cdn_url,
        prompt=prompt + json_instructions,
    )
    cleaned = (text or "").strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    result = _json.loads(cleaned)
    passed = bool(result.get("pass", True))
    reason = str(result.get("reason", "") or "")
    return passed, reason


async def _load_ai_cfg(owner_id: uuid.UUID | None) -> _SearchConfig:
    cfg_owner = owner_id or uuid.UUID(int=0)
    async with SessionLocal() as session:
        pipeline_cfg = await get_or_create_pipeline_settings(session, cfg_owner)
        return _SearchConfig(pipeline_cfg)


async def _fetch_recent_videos(
    owner_id: uuid.UUID | None,
    days: int,
) -> list[tuple[VideoSource, str]]:
    """返回 (VideoSource, keyword_text) 列表。
    keyword_text 通过 CandidateVideo 关联查询，补充模板来源的视频为空字符串。
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    async with SessionLocal() as session:
        stmt = select(VideoSource).where(VideoSource.created_at >= since)
        if owner_id is not None:
            stmt = stmt.where(VideoSource.owner_id == owner_id)
        rows = (await session.scalars(stmt)).all()

        vs_ids = [r.id for r in rows]
        # 关联查 CandidateVideo.keyword_text（候选库导入的视频才有）
        kw_rows = (await session.execute(
            select(CandidateVideo.video_source_id, CandidateVideo.keyword_text)
            .where(CandidateVideo.video_source_id.in_(vs_ids))
        )).all()
        kw_map: dict[uuid.UUID, str] = {r.video_source_id: r.keyword_text for r in kw_rows}

        result = []
        for r in rows:
            vs = VideoSource(**{c.key: getattr(r, c.key) for c in r.__table__.columns})
            keyword = kw_map.get(r.id, "")
            result.append((vs, keyword))
        return result


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

    for i, (vs, keyword) in enumerate(videos, 1):
        prefix = f"[{i}/{len(videos)}] {vs.id}"
        if not vs.local_video_url:
            print(f"{prefix} ⚠ 跳过（无 local_video_url）")
            skipped += 1
            continue

        try:
            prompt = (cfg.ai_review_prompt or "").replace("{keyword}", keyword)
            ok, reason = await _review_with_cdn_url(
                cdn_url=vs.local_video_url,
                prompt=prompt,
                model=cfg.ai_review_model,
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
