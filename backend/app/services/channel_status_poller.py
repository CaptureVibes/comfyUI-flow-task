"""
Channel status poller
=====================
每小时自动触发一次，对所有 source=openapi、status=bound 的
AccountChannelReservation 记录，调用 GET /open-api/v1/channels/authorization
检查授权状态：
  - DISABLED → 将 channel_status 改为 "disabled"
  - ACTIVE    → 将 channel_status 恢复为 "active"
  - NOT_FOUND → 不修改
  - 请求失败  → 跳过，打印警告日志

也可通过 run_channel_status_check() 在任意时刻手动触发一次。
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx
from croniter import croniter
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.account_channel_reservation import AccountChannelReservation

logger = logging.getLogger("app.channel_status_poller")

_CRON_EXPR = "0 * * * *"   # 北京时间每小时整点
_POLL_INTERVAL_SECONDS = 60  # 每分钟检查一次是否到了触发时间
_REQUEST_TIMEOUT = 10.0
_REQUEST_RATE_LIMIT_SEC = 1.0
_TZ = ZoneInfo("Asia/Shanghai")

_poller_task: asyncio.Task | None = None
_poller_stop_event: asyncio.Event | None = None

# 上次触发的 cron key（"YYYY-MM-DD HH:MM"），用于去重
_last_fire_key: str | None = None

# 手动触发时使用的锁，防止手动与自动并发
_run_lock = asyncio.Lock()


def start_channel_status_poller() -> None:
    global _poller_task, _poller_stop_event
    if _poller_task is not None and not _poller_task.done():
        return
    _poller_stop_event = asyncio.Event()
    _poller_task = asyncio.get_running_loop().create_task(
        _poller_loop(_poller_stop_event)
    )
    logger.info("【频道状态轮询】已启动，触发规则：北京时间 %s", _CRON_EXPR)


async def stop_channel_status_poller() -> None:
    global _poller_task, _poller_stop_event
    stop_event, worker = _poller_stop_event, _poller_task
    _poller_stop_event = None
    _poller_task = None
    if stop_event is not None:
        stop_event.set()
    if worker is None:
        return
    worker.cancel()
    try:
        await worker
    except asyncio.CancelledError:
        pass
    logger.info("【频道状态轮询】已停止")


async def run_channel_status_check() -> dict:
    """手动触发一次完整检查，返回 {"checked": N, "changed": N}。"""
    async with _run_lock:
        return await _run_once()


async def _poller_loop(stop_event: asyncio.Event) -> None:
    global _last_fire_key
    # 启动时预填 _last_fire_key，防止重启后立即重复触发
    now_local = datetime.now(timezone.utc).astimezone(_TZ)
    cron = croniter(_CRON_EXPR, now_local)
    prev_local: datetime = cron.get_prev(datetime)
    _last_fire_key = prev_local.strftime("%Y-%m-%d %H:%M")
    logger.debug("【频道状态轮询】预填触发点 %s，启动后不会重复执行", _last_fire_key)

    try:
        while not stop_event.is_set():
            try:
                await _check_and_maybe_fire()
            except Exception:
                logger.exception("【频道状态轮询】调度异常")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=_POLL_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                continue
    except asyncio.CancelledError:
        raise


async def _check_and_maybe_fire() -> None:
    global _last_fire_key
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(_TZ)

    cron = croniter(_CRON_EXPR, now_local)
    prev_local: datetime = cron.get_prev(datetime)
    fire_key = prev_local.strftime("%Y-%m-%d %H:%M")

    # 距上次触发点不超过 _POLL_INTERVAL_SECONDS * 1.5 才算命中
    seconds_since = (now_local - prev_local).total_seconds()
    if seconds_since < 0 or seconds_since >= _POLL_INTERVAL_SECONDS * 1.5:
        return

    if fire_key == _last_fire_key:
        return  # 本触发点已执行过

    _last_fire_key = fire_key
    logger.info("【频道状态轮询】命中触发点 %s（北京时间），开始检查", fire_key)
    async with _run_lock:
        await _run_once()


async def _run_once() -> dict:
    async with SessionLocal() as session:
        result = await session.execute(
            select(AccountChannelReservation).where(
                AccountChannelReservation.source == "openapi",
                AccountChannelReservation.status == "bound",
                AccountChannelReservation.channel_id.isnot(None),
            )
        )
        reservations = list(result.scalars().all())

    checked = len(reservations)
    if not reservations:
        logger.info("【频道状态轮询】无绑定频道，跳过")
        return {"checked": 0, "changed": 0}

    logger.info("【频道状态轮询】开始检查 %d 条绑定频道", checked)

    base_url = settings.open_api_base_url.rstrip("/")
    changed = 0

    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
        for index, r in enumerate(reservations):
            new_status = await _check_one(client, base_url, r)
            if new_status is None:
                pass  # 请求失败或 NOT_FOUND，保持原状
            elif new_status != r.channel_status:
                async with SessionLocal() as session:
                    obj = await session.get(AccountChannelReservation, r.id)
                    if obj is not None:
                        obj.channel_status = new_status
                        await session.commit()
                logger.info(
                    "【频道状态轮询】%s(%s) channel_status: %s → %s",
                    r.platform,
                    r.channel_id,
                    r.channel_status,
                    new_status,
                )
                changed += 1

            # authorization 接口限流：串行调用，最多 1 秒 1 次
            if index < len(reservations) - 1:
                await asyncio.sleep(_REQUEST_RATE_LIMIT_SEC)

    logger.info("【频道状态轮询】本轮完成，共检查 %d 条，更新 %d 条", checked, changed)
    return {"checked": checked, "changed": changed}


async def _check_one(
    client: httpx.AsyncClient,
    base_url: str,
    r: AccountChannelReservation,
) -> str | None:
    try:
        resp = await client.get(
            f"{base_url}/open-api/v1/channels/authorization",
            params={"platform": r.platform, "channel_id": r.channel_id},
        )
        resp.raise_for_status()
        data = resp.json()
        status_val: str = (data.get("data") or {}).get("status", "")
    except Exception as exc:
        logger.warning(
            "【频道状态轮询】查询 %s(%s) 失败: %s",
            r.platform,
            r.channel_id,
            exc,
        )
        return None

    if status_val == "DISABLED":
        return "disabled"
    if status_val == "ACTIVE":
        return "active"
    return None
