"""
Channel name sync scheduler
===========================
每天北京时间 10:00 自动触发，对所有 channel_source=openapi、status=bound 的
AccountChannelReservation 记录，通过 Open API 渠道列表接口同步最新
channel_name 与 username：
  - 找到同 channel_id 的渠道 → 任一字段不一致即更新
  - 找不到 → 不修改
  - 请求失败 → 跳过，打印警告日志

也可通过 run_channel_name_sync() 在任意时刻手动触发一次。
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from croniter import croniter
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.account_channel_reservation import AccountChannelReservation
from app.services.video_publication_service import OpenAPIClient

logger = logging.getLogger("app.channel_name_sync_scheduler")

_CRON_EXPR = "0 10 * * *"   # 北京时间每天 10:00
_POLL_INTERVAL_SECONDS = 60
_REQUEST_RATE_LIMIT_SEC = 0.4
_CHANNEL_PAGE_SIZE = 100
_TZ = ZoneInfo("Asia/Shanghai")

_scheduler_task: asyncio.Task | None = None
_scheduler_stop_event: asyncio.Event | None = None
_last_fire_key: str | None = None
_run_lock = asyncio.Lock()

ProgressCallback = Callable[[dict], Awaitable[None]]
DisconnectChecker = Callable[[], Awaitable[bool]]


class _SyncAborted(Exception):
    pass


def start_channel_name_sync_scheduler() -> None:
    global _scheduler_task, _scheduler_stop_event
    if _scheduler_task is not None and not _scheduler_task.done():
        return
    _scheduler_stop_event = asyncio.Event()
    _scheduler_task = asyncio.get_running_loop().create_task(
        _scheduler_loop(_scheduler_stop_event)
    )
    logger.info("【频道名称同步】已启动，触发规则：北京时间 %s", _CRON_EXPR)


async def stop_channel_name_sync_scheduler() -> None:
    global _scheduler_task, _scheduler_stop_event
    stop_event, worker = _scheduler_stop_event, _scheduler_task
    _scheduler_stop_event = None
    _scheduler_task = None
    if stop_event is not None:
        stop_event.set()
    if worker is None:
        return
    worker.cancel()
    try:
        await worker
    except asyncio.CancelledError:
        pass
    logger.info("【频道名称同步】已停止")


async def run_channel_name_sync(
    progress_callback: ProgressCallback | None = None,
    should_stop: DisconnectChecker | None = None,
) -> dict:
    async with _run_lock:
        return await _run_once(progress_callback=progress_callback, should_stop=should_stop)


async def _scheduler_loop(stop_event: asyncio.Event) -> None:
    global _last_fire_key
    now_local = datetime.now(timezone.utc).astimezone(_TZ)
    cron = croniter(_CRON_EXPR, now_local)
    prev_local: datetime = cron.get_prev(datetime)
    _last_fire_key = prev_local.strftime("%Y-%m-%d %H:%M")

    try:
        while not stop_event.is_set():
            try:
                await _check_and_maybe_fire()
            except Exception:
                logger.exception("【频道名称同步】调度异常")
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

    seconds_since = (now_local - prev_local).total_seconds()
    if seconds_since < 0 or seconds_since >= _POLL_INTERVAL_SECONDS * 1.5:
        return

    if fire_key == _last_fire_key:
        return

    _last_fire_key = fire_key
    logger.info("【频道名称同步】命中触发点 %s（北京时间），开始同步", fire_key)
    async with _run_lock:
        await _run_once()


async def _emit_progress(progress_callback: ProgressCallback | None, payload: dict) -> None:
    if progress_callback is not None:
        await progress_callback(payload)


async def _ensure_not_stopped(should_stop: DisconnectChecker | None) -> None:
    if should_stop is not None and await should_stop():
        raise _SyncAborted


async def _fetch_openapi_channel_info_map(
    client: OpenAPIClient,
    *,
    platform: str,
    should_stop: DisconnectChecker | None,
) -> dict[str, dict[str, str]]:
    """返回 channel_id → {"channel_name": str, "username": str} 映射。"""
    page = 1
    total = 0
    result: dict[str, dict[str, str]] = {}
    usage_types = settings.open_api_channel_usage_types_list or None

    while True:
        await _ensure_not_stopped(should_stop)
        response = await client.fetch_channels(
            platform=platform,
            page=page,
            page_size=_CHANNEL_PAGE_SIZE,
            is_active=None,
            usage_types=usage_types,
        )
        if response.get("code") != 0:
            raise ValueError(response.get("message") or "Open API 返回错误")

        data = response.get("data", {}) if isinstance(response, dict) else {}
        items = data.get("items") or []
        total = max(total, int(data.get("total") or 0))
        for item in items:
            channel_id = str(item.get("channel_id") or "").strip()
            if not channel_id:
                continue
            result[channel_id] = {
                "channel_name": str(item.get("channel_name") or "").strip(),
                "username": str(item.get("username") or "").strip(),
            }

        if len(items) < _CHANNEL_PAGE_SIZE:
            break
        if total and page * _CHANNEL_PAGE_SIZE >= total:
            break

        page += 1
        await asyncio.sleep(_REQUEST_RATE_LIMIT_SEC)

    return result


async def _run_once(
    *,
    progress_callback: ProgressCallback | None = None,
    should_stop: DisconnectChecker | None = None,
) -> dict:
    async with SessionLocal() as session:
        result = await session.execute(
            select(AccountChannelReservation)
            .where(AccountChannelReservation.status == "bound")
            .where(AccountChannelReservation.channel_source == "openapi")
            .where(AccountChannelReservation.channel_id.isnot(None))
            .order_by(AccountChannelReservation.created_at.asc())
        )
        reservations = list(result.scalars().all())

    total = len(reservations)
    processed = 0
    updated = 0
    aborted = False

    await _emit_progress(progress_callback, {
        "event": "started",
        "total": total,
        "message": "开始同步频道名称",
    })

    if not reservations:
        result = {"checked": 0, "updated": 0, "total": 0, "aborted": False}
        await _emit_progress(progress_callback, {
            "event": "completed",
            **result,
            "message": "暂无内部绑定频道，无需同步",
        })
        return result

    grouped: dict[str, list[AccountChannelReservation]] = defaultdict(list)
    for reservation in reservations:
        grouped[str(reservation.platform or "").lower()].append(reservation)

    client = OpenAPIClient()

    try:
        async with SessionLocal() as session:
            for platform, rows in grouped.items():
                try:
                    channel_info_map = await _fetch_openapi_channel_info_map(
                        client,
                        platform=platform,
                        should_stop=should_stop,
                    )
                except _SyncAborted:
                    aborted = True
                    break
                except Exception as exc:
                    logger.warning("【频道名称同步】拉取平台 %s 渠道列表失败: %s", platform, exc)
                    for reservation in rows:
                        processed += 1
                        await _emit_progress(progress_callback, {
                            "event": "progress",
                            "index": processed,
                            "total": total,
                            "updated": updated,
                            "platform": reservation.platform,
                            "channel_id": reservation.channel_id,
                            "previous_channel_name": reservation.channel_name,
                            "current_channel_name": reservation.channel_name,
                            "previous_username": reservation.username,
                            "current_username": reservation.username,
                            "result": "request_failed",
                            "message": f"{platform} 渠道列表拉取失败，无法同步频道名称",
                        })
                    continue

                for reservation in rows:
                    try:
                        await _ensure_not_stopped(should_stop)
                    except _SyncAborted:
                        aborted = True
                        break

                    previous_name = reservation.channel_name or ""
                    previous_username = reservation.username or ""
                    current_name = previous_name
                    current_username = previous_username
                    result_type = "not_found"

                    channel_id = str(reservation.channel_id or "").strip()
                    if channel_id in channel_info_map:
                        info = channel_info_map[channel_id]
                        current_name = info.get("channel_name") or ""
                        current_username = info.get("username") or ""
                        name_changed = current_name != previous_name
                        username_changed = current_username != previous_username
                        if name_changed or username_changed:
                            obj = await session.get(AccountChannelReservation, reservation.id)
                            if obj is not None:
                                if name_changed:
                                    obj.channel_name = current_name or None
                                if username_changed:
                                    obj.username = current_username or None
                                await session.commit()
                            updated += 1
                            result_type = "updated"
                        else:
                            result_type = "unchanged"

                    processed += 1
                    await _emit_progress(progress_callback, {
                        "event": "progress",
                        "index": processed,
                        "total": total,
                        "updated": updated,
                        "platform": reservation.platform,
                        "channel_id": reservation.channel_id,
                        "previous_channel_name": previous_name,
                        "current_channel_name": current_name,
                        "previous_username": previous_username,
                        "current_username": current_username,
                        "result": result_type,
                        "message": "频道名称同步完成",
                    })

                if aborted:
                    break
    finally:
        pass

    result = {"checked": processed, "updated": updated, "total": total, "aborted": aborted}
    await _emit_progress(progress_callback, {
        "event": "completed" if not aborted else "aborted",
        **result,
        "message": (
            f"已同步 {processed} / {total} 个频道，更新 {updated} 个名称"
            if total
            else "暂无内部绑定频道，无需同步"
        ),
    })
    return result
