"""
Account tier evaluation scheduler
=================================
每天北京时间 09:00 自动触发，对所有 AI 博主账号执行两步分级：

1. 实验号 (test) → 常规号 (dev)
   条件：过去 7 条发布的均播 ≥ 700，且过去 7 天内发布次数 ≥ 6。

2. 常规号 (dev) → 正式号 (prod) 随机扩量
   每天从当前 dev 中随机选 round(uniform(0, 6%) * len(prod)) 个晋升 prod。
   N=0 时跳过（冷启动需先通过 accounts 页面批量修改属性手动设置 prod）。

也可通过 run_account_tier_evaluation() 在任意时刻手动触发一次。
"""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from croniter import croniter
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.account import Account
from app.models.video_publication import VideoPublication
from app.models.video_task import VideoSubTask, VideoTask

logger = logging.getLogger("app.account_tier_scheduler")

_CRON_EXPR = "0 9 * * *"   # 北京时间每天 09:00（早于 channel_name_sync 10:00）
_POLL_INTERVAL_SECONDS = 60
_TZ = ZoneInfo("Asia/Shanghai")

# 晋级阈值
_DEV_AVG_VIEWS_MIN = 700      # 过去 7 条均播
_DEV_RECENT_VIDEO_MIN = 6     # 过去 7 天发布次数
_DEV_LOOKBACK_VIDEOS = 7
_DEV_LOOKBACK_DAYS = 7
_PROD_DAILY_RATE_MAX = 0.06   # 每日随机最大比例 (0~6%)

_scheduler_task: asyncio.Task | None = None
_scheduler_stop_event: asyncio.Event | None = None
_last_fire_key: str | None = None
_run_lock = asyncio.Lock()


def start_account_tier_scheduler() -> None:
    global _scheduler_task, _scheduler_stop_event
    if _scheduler_task is not None and not _scheduler_task.done():
        return
    _scheduler_stop_event = asyncio.Event()
    _scheduler_task = asyncio.get_running_loop().create_task(
        _scheduler_loop(_scheduler_stop_event)
    )
    logger.info("【账号分级】调度器已启动，触发规则：北京时间 %s", _CRON_EXPR)


async def stop_account_tier_scheduler() -> None:
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
    logger.info("【账号分级】调度器已停止")


async def run_account_tier_evaluation() -> dict:
    """手动触发一次评估，返回 {promoted_to_dev, promoted_to_prod}。"""
    async with _run_lock:
        return await _run_once()


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
                logger.exception("【账号分级】调度异常")
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
    logger.info("【账号分级】命中触发点 %s（北京时间），开始评估", fire_key)
    async with _run_lock:
        await _run_once()


# ── 核心逻辑 ─────────────────────────────────────────────────────────────────

def _to_int(val) -> int:
    try:
        n = int(val)
        return n if n > 0 else 0
    except (TypeError, ValueError):
        return 0


def _publication_views(pub: VideoPublication) -> int:
    """从 metrics_snapshot.channels 累加该发布的总播放量。"""
    snapshot = pub.metrics_snapshot
    if not isinstance(snapshot, dict):
        return 0
    channels = snapshot.get("channels") or []
    total = 0
    for ch in channels:
        if not isinstance(ch, dict):
            continue
        stats = ch.get("stats") or {}
        platform = str(ch.get("platform") or "").lower()
        if platform == "youtube":
            total += _to_int(stats.get("views"))
        else:
            total += _to_int(stats.get("view_count") or stats.get("views"))
    return total


async def _evaluate_test_to_dev(session) -> int:
    """扫描 test 账号，满足条件则升级为 dev。返回晋级数量。"""
    test_accounts = list((await session.execute(
        select(Account).where(Account.account_tier == "test")
    )).scalars().all())
    if not test_accounts:
        return 0

    now = datetime.now(timezone.utc)
    cutoff_recent = now - timedelta(days=_DEV_LOOKBACK_DAYS)
    promoted = 0

    for account in test_accounts:
        # 过去 7 条 completed/partial 发布（按 completed_at desc）
        last_pubs = list((await session.execute(
            select(VideoPublication)
            .join(VideoSubTask, VideoSubTask.id == VideoPublication.sub_task_id)
            .join(VideoTask, VideoTask.id == VideoSubTask.task_id)
            .where(VideoTask.account_id == account.id)
            .where(VideoPublication.status.in_(["completed", "partial"]))
            .where(VideoPublication.completed_at.isnot(None))
            .order_by(VideoPublication.completed_at.desc())
            .limit(_DEV_LOOKBACK_VIDEOS)
        )).scalars().all())
        if len(last_pubs) < _DEV_LOOKBACK_VIDEOS:
            continue

        avg_views = sum(_publication_views(p) for p in last_pubs) / _DEV_LOOKBACK_VIDEOS
        if avg_views < _DEV_AVG_VIEWS_MIN:
            continue

        # 过去 7 天内的发布数
        recent_count = await session.scalar(
            select(func.count(VideoPublication.id))
            .join(VideoSubTask, VideoSubTask.id == VideoPublication.sub_task_id)
            .join(VideoTask, VideoTask.id == VideoSubTask.task_id)
            .where(VideoTask.account_id == account.id)
            .where(VideoPublication.status.in_(["completed", "partial"]))
            .where(VideoPublication.completed_at >= cutoff_recent)
        )
        if (recent_count or 0) < _DEV_RECENT_VIDEO_MIN:
            continue

        account.account_tier = "dev"
        promoted += 1
        logger.info(
            "【账号分级】test→dev: account_id=%s name=%s avg_views=%.1f recent=%s",
            account.id, account.account_name, avg_views, recent_count,
        )

    if promoted:
        await session.commit()
    return promoted


async def _evaluate_dev_to_prod(session) -> int:
    """从 dev 中随机晋升一定比例到 prod。返回晋级数量。"""
    prod_count = await session.scalar(
        select(func.count(Account.id)).where(Account.account_tier == "prod")
    ) or 0
    if prod_count <= 0:
        logger.info("【账号分级】当前正式号数量为 0，跳过 dev→prod 随机晋级（需先冷启动手动设置）")
        return 0

    rate = random.uniform(0, _PROD_DAILY_RATE_MAX)
    target = round(rate * prod_count)
    if target <= 0:
        logger.info(
            "【账号分级】今日随机晋级数 = 0（rate=%.4f * prod_count=%d）",
            rate, prod_count,
        )
        return 0

    dev_accounts = list((await session.execute(
        select(Account).where(Account.account_tier == "dev")
    )).scalars().all())
    if not dev_accounts:
        logger.info("【账号分级】无可晋升的常规号，跳过 dev→prod")
        return 0

    pick = min(target, len(dev_accounts))
    chosen = random.sample(dev_accounts, pick)
    for account in chosen:
        account.account_tier = "prod"
        logger.info(
            "【账号分级】dev→prod: account_id=%s name=%s",
            account.id, account.account_name,
        )
    await session.commit()
    logger.info(
        "【账号分级】今日 dev→prod 完成：rate=%.4f, prod_count=%d, target=%d, picked=%d",
        rate, prod_count, target, pick,
    )
    return pick


async def _run_once() -> dict:
    async with SessionLocal() as session:
        promoted_dev = await _evaluate_test_to_dev(session)
        promoted_prod = await _evaluate_dev_to_prod(session)

    result = {"promoted_to_dev": promoted_dev, "promoted_to_prod": promoted_prod}
    logger.info("【账号分级】本轮完成：%s", result)
    return result
