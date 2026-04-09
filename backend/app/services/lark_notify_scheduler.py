"""
lark_notify_scheduler.py
========================
每天 UTC 02:00 统计昨日发布视频数量并推送 Lark 通知。

统计口径：
  - video_publications.completed_at 落在昨日（UTC）
  - status IN ('completed', 'partial')

通知内容：
  - 总发布数
  - 成功（completed）/ 部分成功（partial）分项
  - 各账号明细（账号名 + 数量）
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

import httpx
from sqlalchemy import func, select

from app.core.config import settings
from app.db.session import SessionLocal

logger = logging.getLogger("app.lark_notify_scheduler")

_NOTIFY_HOUR_UTC = 2       # 每天 UTC 02:00 触发
_POLL_INTERVAL   = 60.0    # 每分钟检查一次

_scheduler_task: asyncio.Task | None = None
_scheduler_stop_event: asyncio.Event | None = None


# ── 启动 / 停止 ──────────────────────────────────────────────────────────────

def start_lark_notify_scheduler() -> None:
    global _scheduler_task, _scheduler_stop_event
    if _scheduler_task is not None and not _scheduler_task.done():
        return
    if not settings.lark_webhook_url:
        logger.info("【Lark通知】LARK_WEBHOOK_URL 未配置，跳过启动")
        return
    _scheduler_stop_event = asyncio.Event()
    _scheduler_task = asyncio.get_running_loop().create_task(
        _scheduler_loop(_scheduler_stop_event)
    )
    logger.info("【Lark通知】调度器已启动，每天 UTC %02d:00 发送日报", _NOTIFY_HOUR_UTC)


async def stop_lark_notify_scheduler() -> None:
    global _scheduler_task, _scheduler_stop_event
    stop_event, worker = _scheduler_stop_event, _scheduler_task
    _scheduler_stop_event = None
    _scheduler_task = None
    if stop_event:
        stop_event.set()
    if worker is None:
        return
    worker.cancel()
    try:
        await worker
    except asyncio.CancelledError:
        pass
    logger.info("【Lark通知】调度器已停止")


# ── 主循环 ───────────────────────────────────────────────────────────────────

async def _scheduler_loop(stop_event: asyncio.Event) -> None:
    last_triggered_date: date | None = None
    try:
        while not stop_event.is_set():
            now_utc = datetime.now(timezone.utc)
            today = now_utc.date()

            # 当前小时 == 触发小时，且今天还没触发过
            if now_utc.hour == _NOTIFY_HOUR_UTC and last_triggered_date != today:
                last_triggered_date = today
                try:
                    await _send_daily_report()
                except Exception:
                    logger.exception("【Lark通知】发送日报失败")

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=_POLL_INTERVAL)
            except asyncio.TimeoutError:
                pass
    except asyncio.CancelledError:
        raise


# ── 统计 + 推送 ──────────────────────────────────────────────────────────────

async def _send_daily_report() -> None:
    from app.models.video_publication import VideoPublication
    from app.models.video_task import VideoSubTask, VideoTask
    from app.models.account import Account

    yesterday = date.today() - timedelta(days=1)
    day_start = datetime(yesterday.year, yesterday.month, yesterday.day, tzinfo=timezone.utc)
    day_end   = day_start + timedelta(days=1)

    logger.info("【Lark通知】统计日期: %s", yesterday)

    async with SessionLocal() as session:
        # 昨日 completed_at 在范围内、状态 completed/partial 的所有发布记录
        rows = (await session.execute(
            select(VideoPublication, Account.account_name)
            .join(VideoSubTask, VideoPublication.sub_task_id == VideoSubTask.id)
            .join(VideoTask,    VideoSubTask.task_id == VideoTask.id)
            .outerjoin(Account, VideoTask.account_id == Account.id)
            .where(
                VideoPublication.status.in_(["completed", "partial"]),
                VideoPublication.completed_at >= day_start,
                VideoPublication.completed_at <  day_end,
            )
        )).all()

    total     = len(rows)
    completed = sum(1 for r, _ in rows if r.status == "completed")
    partial   = sum(1 for r, _ in rows if r.status == "partial")

    # 按账号聚合
    account_counts: dict[str, int] = {}
    for _, account_name in rows:
        name = account_name or "未知账号"
        account_counts[name] = account_counts.get(name, 0) + 1

    logger.info(
        "【Lark通知】昨日发布统计: 总计 %d，completed %d，partial %d，账号 %d 个",
        total, completed, partial, len(account_counts),
    )

    message = _build_message(yesterday, total, completed, partial, account_counts)
    await _send_lark(message)


def _build_message(
    day: date,
    total: int,
    completed: int,
    partial: int,
    account_counts: dict[str, int],
) -> dict:
    date_str = day.strftime("%Y-%m-%d")

    if total == 0:
        summary = f"📭 昨日（{date_str}）暂无视频发布记录"
    else:
        summary = f"📊 昨日（{date_str}）共发布 **{total}** 条视频"

    lines = [summary]
    if total > 0:
        lines.append(f"✅ 完全成功：{completed} 条　⚠️ 部分成功：{partial} 条")
        lines.append("")
        lines.append("**各账号明细：**")
        for name, cnt in sorted(account_counts.items(), key=lambda x: -x[1]):
            lines.append(f"• {name}：{cnt} 条")

    content_text = "\n".join(lines)

    return {
        "msg_type": "interactive",
        "card": {
            "schema": "2.0",
            "body": {
                "elements": [
                    {
                        "tag": "markdown",
                        "content": content_text,
                    }
                ]
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"视频发布日报 · {date_str}",
                },
                "template": "blue" if total > 0 else "grey",
            },
        },
    }


async def _send_lark(payload: dict) -> None:
    url = settings.lark_webhook_url
    if not url:
        return
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        result = resp.json()
        if result.get("code") not in (0, None):
            logger.warning("【Lark通知】推送响应异常: %s", result)
        else:
            logger.info("【Lark通知】推送成功")
