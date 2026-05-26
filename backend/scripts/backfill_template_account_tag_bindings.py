"""回填模板↔账号 tag 的绑定关系。

问题背景：
  - 列表页"X 个视频 / Y/Z 模板"对不上，因为 _count_account_templates 要求
    模板必须有一条 video_source_tags 行 (video_ai_template_id=tpl.id, tag_id ∈ account_tags)。
  - 历史上：vendor 补充 / 候选库导入 / 手动建模板等路径下，模板要么绑了"博主名 tag"
    要么根本没绑账号现在的 tag → 计数偏少。

逻辑：
  对每个账号：
    对它绑定的每个博主下的每个模板 tpl：
      对账号挂的每个 tag at：
        若 video_source_tags 里不存在 (video_ai_template_id=tpl.id, tag_id=at.tag_id)，
        则插入一行 (video_source_id=tpl.video_source_id, video_ai_template_id=tpl.id, tag_id=at.tag_id)

用法：
    cd backend
    uv run python scripts/backfill_template_account_tag_bindings.py
    uv run python scripts/backfill_template_account_tag_bindings.py --dry-run
    uv run python scripts/backfill_template_account_tag_bindings.py --owner-id <uuid>
    uv run python scripts/backfill_template_account_tag_bindings.py --account-id <uuid>
    uv run python scripts/backfill_template_account_tag_bindings.py --no-lark
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from sqlalchemy import text

from app.core.config import settings
from app.db.session import SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("backfill_template_account_tag_bindings")


_PREVIEW_SQL = text(
    """
    SELECT
      tpl.id AS template_id,
      tpl.video_source_id,
      at.account_id,
      at.tag_id,
      t.name AS tag_name,
      COALESCE(tpl.owner_id, vs.owner_id) AS effective_owner_id
    FROM video_ai_templates tpl
    JOIN video_sources vs ON vs.id = tpl.video_source_id
    JOIN account_tiktok_bloggers abb ON vs.tiktok_blogger_id = abb.tiktok_blogger_id
    JOIN account_tags at ON at.account_id = abb.account_id
    JOIN tags t ON t.id = at.tag_id
    WHERE (CAST(:account_id AS uuid) IS NULL OR abb.account_id = CAST(:account_id AS uuid))
      AND (CAST(:owner_id AS uuid) IS NULL OR COALESCE(tpl.owner_id, vs.owner_id) = CAST(:owner_id AS uuid))
      AND NOT EXISTS (
        SELECT 1 FROM video_source_tags vst
        WHERE vst.video_ai_template_id = tpl.id
          AND vst.tag_id = at.tag_id
      )
    """
)


_INSERT_SQL = text(
    """
    INSERT INTO video_source_tags
      (id, owner_id, video_source_id, video_ai_template_id, tag_id, created_at)
    SELECT
      gen_random_uuid(),
      COALESCE(tpl.owner_id, vs.owner_id),
      tpl.video_source_id,
      tpl.id,
      at.tag_id,
      now()
    FROM video_ai_templates tpl
    JOIN video_sources vs ON vs.id = tpl.video_source_id
    JOIN account_tiktok_bloggers abb ON vs.tiktok_blogger_id = abb.tiktok_blogger_id
    JOIN account_tags at ON at.account_id = abb.account_id
    WHERE (CAST(:account_id AS uuid) IS NULL OR abb.account_id = CAST(:account_id AS uuid))
      AND (CAST(:owner_id AS uuid) IS NULL OR COALESCE(tpl.owner_id, vs.owner_id) = CAST(:owner_id AS uuid))
      AND NOT EXISTS (
        SELECT 1 FROM video_source_tags vst
        WHERE vst.video_ai_template_id = tpl.id
          AND vst.tag_id = at.tag_id
      )
    RETURNING id, video_ai_template_id, tag_id
    """
)


async def _preview(account_id: uuid.UUID | None, owner_id: uuid.UUID | None) -> dict:
    """返回 {total: int, by_account: {account_id: count}, sample: [...]}"""
    async with SessionLocal() as session:
        rows = (await session.execute(
            _PREVIEW_SQL,
            {"account_id": account_id, "owner_id": owner_id},
        )).all()

    by_account: dict[str, int] = {}
    by_tag: dict[str, dict] = {}  # tag_id -> {name, count}
    for r in rows:
        a_id = str(r.account_id)
        by_account[a_id] = by_account.get(a_id, 0) + 1
        t_id = str(r.tag_id)
        if t_id not in by_tag:
            by_tag[t_id] = {"name": r.tag_name or "(无名)", "count": 0}
        by_tag[t_id]["count"] += 1

    return {
        "total": len(rows),
        "by_account": by_account,
        "by_tag": by_tag,
        "sample": [
            {
                "template_id": str(r.template_id),
                "tag_name": r.tag_name,
                "account_id": str(r.account_id),
            }
            for r in rows[:10]
        ],
    }


async def _execute_insert(
    account_id: uuid.UUID | None, owner_id: uuid.UUID | None,
) -> int:
    """实际执行 INSERT，返回插入的行数。"""
    async with SessionLocal() as session:
        result = await session.execute(
            _INSERT_SQL,
            {"account_id": account_id, "owner_id": owner_id},
        )
        inserted = list(result.all())
        await session.commit()
    return len(inserted)


async def _send_lark_summary(
    inserted_count: int,
    account_count: int,
    tag_count: int,
    dry_run: bool,
    scope_desc: str,
) -> None:
    if not settings.lark_webhook_url:
        logger.info("LARK_WEBHOOK_URL 未配置，跳过通知")
        return

    title_prefix = "[dry-run] " if dry_run else ""
    action = "待补绑" if dry_run else "已补绑"
    lines = [
        f"扫描范围：{scope_desc}",
        "",
        f"📦 {action} **{inserted_count}** 条 video_source_tags",
        f"👤 涉及账号数：{account_count}",
        f"🏷️ 涉及标签数：{tag_count}",
    ]

    body = {
        "msg_type": "interactive",
        "card": {
            "schema": "2.0",
            "body": {"elements": [{"tag": "markdown", "content": "\n".join(lines)}]},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"{title_prefix}模板↔账号 tag 绑定回填 · " +
                               datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                },
                "template": "grey" if dry_run else ("blue" if inserted_count > 0 else "grey"),
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


async def _run(
    account_id: uuid.UUID | None,
    owner_id: uuid.UUID | None,
    dry_run: bool,
    send_lark: bool,
) -> None:
    scope_parts = []
    if account_id:
        scope_parts.append(f"account_id={account_id}")
    if owner_id:
        scope_parts.append(f"owner_id={owner_id}")
    scope_desc = " ; ".join(scope_parts) if scope_parts else "全表"
    logger.info("范围: %s (dry_run=%s)", scope_desc, dry_run)

    preview = await _preview(account_id, owner_id)
    total = preview["total"]
    logger.info("候选 video_source_tags 行数：%d", total)
    logger.info("涉及账号 %d 个、标签 %d 个", len(preview["by_account"]), len(preview["by_tag"]))
    if preview["sample"]:
        logger.info("示例（最多 10 条）：")
        for s in preview["sample"]:
            logger.info("  tpl=%s tag=%s account=%s", s["template_id"], s["tag_name"], s["account_id"])

    if total == 0:
        logger.info("没有需要补绑的，结束")
        if send_lark and not dry_run:
            await _send_lark_summary(0, 0, 0, dry_run=False, scope_desc=scope_desc)
        return

    if dry_run:
        logger.info("[dry-run] 不执行 INSERT，结束")
        if send_lark:
            await _send_lark_summary(
                total, len(preview["by_account"]), len(preview["by_tag"]),
                dry_run=True, scope_desc=scope_desc,
            )
        return

    inserted = await _execute_insert(account_id, owner_id)
    logger.info("实际插入 %d 行", inserted)
    if send_lark:
        await _send_lark_summary(
            inserted, len(preview["by_account"]), len(preview["by_tag"]),
            dry_run=False, scope_desc=scope_desc,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="回填模板↔账号 tag 的 video_source_tags 绑定")
    parser.add_argument("--account-id", help="只处理指定账号（UUID）")
    parser.add_argument("--owner-id", help="只处理指定 owner（UUID）")
    parser.add_argument("--dry-run", action="store_true", help="只扫描 + 报告，不插入")
    parser.add_argument("--no-lark", action="store_true", help="不发 Lark 通知")
    args = parser.parse_args()

    asyncio.run(_run(
        account_id=uuid.UUID(args.account_id) if args.account_id else None,
        owner_id=uuid.UUID(args.owner_id) if args.owner_id else None,
        dry_run=args.dry_run,
        send_lark=not args.no_lark,
    ))


if __name__ == "__main__":
    main()
