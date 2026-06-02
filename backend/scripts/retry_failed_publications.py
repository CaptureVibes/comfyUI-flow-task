"""重新发布指定 UTC 日期内 status=failed 的 video_publications。

失败的根因是 request_payload.video_url 是未签名的 GCS 链接，外部平台拉不到视频。
处理流程：
  1. 找出 UTC 当日 status='failed' 的 publication
  2. 对 request_payload 里的 video_url / original_video_url 做签名（GCS 才签，
     CDN 跳过；已签且新鲜也跳过）
  3. 把签好的 payload 回写到 video_publications.request_payload
  4. 把 sub_task.status 强制改回 publish_failed（如果不是的话），然后调
     VideoPublicationService.retry_publication 走标准重发链路
  5. 跑完汇总 Lark 通知

用法（默认昨天 UTC）：
    cd backend
    uv run python scripts/retry_failed_publications.py
    uv run python scripts/retry_failed_publications.py --date 2026-05-24
    uv run python scripts/retry_failed_publications.py --date 2026-05-24 --dry-run
    uv run python scripts/retry_failed_publications.py --date 2026-05-24 --no-lark
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.video_publication import VideoPublication
from app.models.video_task import VideoSubTask
from app.services.video_publication_service import VideoPublicationService
from app.utils.gcs_download import is_gcs_url
from app.utils.gcs_signing import sign_publish_url

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("retry_failed_publications")


async def _list_failed_publication_ids(target_date: date) -> list[uuid.UUID]:
    """status='failed' 且 created_at 落在 target_date (UTC) 当天的记录。

    用 created_at 而不是 updated_at：retry_publication 会刷新 updated_at，
    重跑后想找原始那批失败记录就找不到了。
    """
    start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    async with SessionLocal() as session:
        stmt = (
            select(VideoPublication.id)
            .where(VideoPublication.status == "failed")
            .where(VideoPublication.created_at >= start)
            .where(VideoPublication.created_at < end)
            .order_by(VideoPublication.created_at.asc())
        )
        return list((await session.execute(stmt)).scalars().all())


async def _fix_payload_and_retry(pub_id: uuid.UUID, dry_run: bool) -> dict:
    """对单条 publication 做"签名 + 回写 payload + 标记 sub_task + 调 retry"。

    返回 {status, pub_id, reason}；status ∈ {success, failed, skipped}。
    """
    # 阶段 1：读 + 改 + 写
    url_changed = False
    sub_task_state_flipped = False
    async with SessionLocal() as session:
        pub = await session.get(VideoPublication, pub_id)
        if pub is None:
            return {"status": "skipped", "pub_id": str(pub_id), "reason": "记录不存在"}
        if not pub.request_payload:
            return {"status": "skipped", "pub_id": str(pub_id), "reason": "无 request_payload"}

        payload = dict(pub.request_payload)
        for key in ("video_url", "original_video_url"):
            old = payload.get(key)
            if not old:
                continue
            if not is_gcs_url(old):
                continue
            new = sign_publish_url(old)
            if new and new != old:
                payload[key] = new
                url_changed = True

        sub_task = await session.get(VideoSubTask, pub.sub_task_id)
        if sub_task is None:
            return {"status": "skipped", "pub_id": str(pub_id), "reason": "sub_task 不存在"}
        need_flip_sub_task = sub_task.status != "publish_failed"

        if dry_run:
            return {
                "status": "skipped",
                "pub_id": str(pub_id),
                "reason": (
                    f"[dry-run] 待签名={url_changed} 需翻 sub_task={need_flip_sub_task} "
                    f"sub_task_status={sub_task.status}"
                ),
            }

        if url_changed:
            pub.request_payload = payload
        if need_flip_sub_task:
            sub_task.status = "publish_failed"
            sub_task_state_flipped = True
        if url_changed or need_flip_sub_task:
            await session.commit()

    # 阶段 2：触发重发（新 session）
    try:
        async with SessionLocal() as session:
            service = VideoPublicationService(session)
            await service.retry_publication(pub_id, owner_id=None)
    except Exception as exc:
        logger.warning("retry_publication %s 抛错: %s", pub_id, exc)
        return {
            "status": "failed",
            "pub_id": str(pub_id),
            "reason": f"retry 调用失败: {str(exc)[:200]}",
        }

    parts = []
    if url_changed:
        parts.append("已签名")
    if sub_task_state_flipped:
        parts.append("sub_task→publish_failed")
    return {
        "status": "success",
        "pub_id": str(pub_id),
        "reason": "+".join(parts) if parts else "无变更直接重发",
    }


async def _send_lark_summary(target_date: date, results: list[dict]) -> None:
    if not settings.lark_webhook_url:
        logger.info("LARK_WEBHOOK_URL 未配置，跳过通知")
        return

    total = len(results)
    success = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")
    skipped = sum(1 for r in results if r["status"] == "skipped")

    lines = [
        f"扫描 {target_date.isoformat()} (UTC) 失败发布记录：**{total}** 条",
        "",
        f"✅ 重发成功：{success}",
        f"❌ 重发失败：{failed}",
        f"⏭️ 跳过：{skipped}",
    ]
    failed_examples = [r for r in results if r["status"] == "failed"][:5]
    if failed_examples:
        lines.append("")
        lines.append("**失败示例（最多 5 条）：**")
        for r in failed_examples:
            lines.append(f"• `{r['pub_id'][:8]}…` {r['reason']}")

    body = {
        "msg_type": "interactive",
        "card": {
            "schema": "2.0",
            "body": {"elements": [{"tag": "markdown", "content": "\n".join(lines)}]},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"失败发布重试 · {target_date.isoformat()}",
                },
                "template": "blue" if success > 0 and failed == 0 else ("red" if failed > 0 else "grey"),
            },
        },
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(settings.lark_webhook_url, json=body)
            resp.raise_for_status()
            logger.info("Lark 通知已推送")
    except Exception as exc:
        logger.warning("Lark 通知推送失败: %s", exc)


async def _run(target_date: date, dry_run: bool, send_lark: bool) -> None:
    logger.info("扫描 UTC %s 的 failed publications (dry_run=%s)", target_date, dry_run)
    pub_ids = await _list_failed_publication_ids(target_date)
    logger.info("命中 %d 条", len(pub_ids))

    results: list[dict] = []
    for i, pid in enumerate(pub_ids, 1):
        logger.info("[%d/%d] 处理 %s", i, len(pub_ids), pid)
        try:
            r = await _fix_payload_and_retry(pid, dry_run=dry_run)
        except Exception as exc:
            logger.exception("处理 %s 抛未捕获异常", pid)
            r = {"status": "failed", "pub_id": str(pid), "reason": f"未捕获: {str(exc)[:200]}"}
        results.append(r)
        logger.info("[%d/%d] → %s | %s", i, len(pub_ids), r["status"], r.get("reason"))

    success = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    logger.info(
        "完成：total=%d success=%d failed=%d skipped=%d",
        len(results), success, failed, skipped,
    )

    if send_lark and not dry_run:
        await _send_lark_summary(target_date, results)
    elif dry_run:
        logger.info("[dry-run] 跳过 Lark 通知")


def main() -> None:
    parser = argparse.ArgumentParser(description="重新发布指定 UTC 日期的 failed publications")
    parser.add_argument(
        "--date",
        help="UTC 日期 YYYY-MM-DD（默认昨天 UTC）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只扫描 + 报告，不签名、不改库、不调 retry、不发 Lark",
    )
    parser.add_argument(
        "--no-lark",
        action="store_true",
        help="不发 Lark 通知（dry-run 默认就不发）",
    )
    args = parser.parse_args()

    if args.date:
        target_date = date.fromisoformat(args.date)
    else:
        target_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()

    asyncio.run(_run(target_date, dry_run=args.dry_run, send_lark=not args.no_lark))


if __name__ == "__main__":
    main()
