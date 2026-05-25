"""把所有 kol_provision_status='pending' 且 kol_user_id 为空的账号统一重试 KOL 创建。

实际场景：原本的 provision 在 Account 创建那一瞬同步调，进程崩了 / 超时 / 网络抖动等
导致状态卡在 ``pending``。这个脚本兜底一次性重新调站内平台 KOL 创建接口。

用法（默认全量）：
    cd backend
    uv run python scripts/retry_pending_kol.py
    uv run python scripts/retry_pending_kol.py --dry-run
    uv run python scripts/retry_pending_kol.py --owner-id <uuid>
    uv run python scripts/retry_pending_kol.py --no-lark
    uv run python scripts/retry_pending_kol.py --concurrency 5

注意：
- 已有 kol_user_id 的账号会被 provision_kol_for_account 自己短路跳过（幂等）
- 单条失败不影响其它；最终汇总 + Lark 通知
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
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.account import Account
from app.services.kol_service import provision_kol_for_account

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("retry_pending_kol")


async def _list_pending_accounts(owner_id: uuid.UUID | None) -> list[uuid.UUID]:
    """kol_provision_status='pending' 且 kol_user_id 为空的账号。"""
    async with SessionLocal() as session:
        stmt = (
            select(Account.id)
            .where(Account.kol_provision_status == "pending")
            .where(Account.kol_user_id.is_(None))
            .order_by(Account.created_at.asc())
        )
        if owner_id is not None:
            stmt = stmt.where(Account.owner_id == owner_id)
        return list((await session.execute(stmt)).scalars().all())


async def _retry_one(account_id: uuid.UUID, dry_run: bool) -> dict:
    """返回 {status, account_id, kol_user_id, reason}；
    status ∈ {success, failed, skipped}。"""
    if dry_run:
        return {"status": "skipped", "account_id": str(account_id), "reason": "[dry-run]"}

    # provision_kol_for_account 自带 session + try/except + 幂等
    try:
        await provision_kol_for_account(account_id)
    except Exception as exc:
        return {"status": "failed", "account_id": str(account_id), "reason": f"未捕获异常: {str(exc)[:200]}"}

    # 读回最新状态判定结果
    async with SessionLocal() as session:
        acc = await session.get(Account, account_id)
        if acc is None:
            return {"status": "failed", "account_id": str(account_id), "reason": "账号已被删除"}
        if acc.kol_user_id:
            return {
                "status": "success",
                "account_id": str(account_id),
                "kol_user_id": acc.kol_user_id,
                "reason": acc.kol_provision_status,
            }
        return {
            "status": "failed",
            "account_id": str(account_id),
            "reason": (acc.kol_provision_error or "未知，仍无 kol_user_id")[:200],
        }


async def _send_lark_summary(results: list[dict]) -> None:
    if not settings.lark_webhook_url:
        logger.info("LARK_WEBHOOK_URL 未配置，跳过通知")
        return

    total = len(results)
    success = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")
    skipped = sum(1 for r in results if r["status"] == "skipped")

    lines = [
        f"扫描卡在 pending 状态的 KOL 账号：**{total}** 条",
        "",
        f"✅ 创建成功：{success}",
        f"❌ 仍然失败：{failed}",
        f"⏭️ 跳过：{skipped}",
    ]
    failed_examples = [r for r in results if r["status"] == "failed"][:5]
    if failed_examples:
        lines.append("")
        lines.append("**失败示例（最多 5 条）：**")
        for r in failed_examples:
            lines.append(f"• `{r['account_id'][:8]}…` {r['reason']}")

    body = {
        "msg_type": "interactive",
        "card": {
            "schema": "2.0",
            "body": {"elements": [{"tag": "markdown", "content": "\n".join(lines)}]},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "Pending KOL 重试 · " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
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


async def _run(
    owner_id: uuid.UUID | None,
    dry_run: bool,
    send_lark: bool,
    interval_sec: float,
) -> None:
    logger.info(
        "扫描 kol_provision_status='pending' 且 kol_user_id IS NULL 的账号 "
        "(dry_run=%s, interval=%.2fs)",
        dry_run, interval_sec,
    )
    account_ids = await _list_pending_accounts(owner_id)
    total = len(account_ids)
    logger.info("命中 %d 条", total)
    if not account_ids:
        return

    # 严格串行：下游 KOL 接口同样吃 100 req/min 共享 quota，
    # 一次只发一个，加间隔留缓冲。
    results: list[dict] = []
    for idx, aid in enumerate(account_ids, 1):
        try:
            r = await _retry_one(aid, dry_run=dry_run)
        except Exception as exc:
            r = {"status": "failed", "account_id": str(aid), "reason": f"wrapper 异常: {str(exc)[:200]}"}
        results.append(r)
        logger.info("[%d/%d] %s → %s | %s", idx, total, aid, r["status"], r.get("reason"))
        if idx < total and interval_sec > 0:
            await asyncio.sleep(interval_sec)

    success = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    logger.info("完成：total=%d success=%d failed=%d skipped=%d", len(results), success, failed, skipped)

    if send_lark and not dry_run:
        await _send_lark_summary(results)
    elif dry_run:
        logger.info("[dry-run] 跳过 Lark 通知")


def main() -> None:
    parser = argparse.ArgumentParser(description="重试所有 pending 状态的 KOL 创建（严格串行）")
    parser.add_argument("--owner-id", help="只处理指定 owner 的账号（UUID）")
    parser.add_argument("--dry-run", action="store_true", help="只扫描，不调 KOL 接口")
    parser.add_argument("--no-lark", action="store_true", help="不发 Lark 通知")
    parser.add_argument(
        "--interval-sec",
        type=float,
        default=1.0,
        help="每条调用之间的间隔秒数（默认 1.0；下游限流 100 req/min，留缓冲）",
    )
    args = parser.parse_args()

    owner_id = uuid.UUID(args.owner_id) if args.owner_id else None
    asyncio.run(_run(
        owner_id=owner_id,
        dry_run=args.dry_run,
        send_lark=not args.no_lark,
        interval_sec=args.interval_sec,
    ))


if __name__ == "__main__":
    main()
