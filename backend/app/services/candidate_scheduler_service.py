"""候选库定时抓取调度器

按北京时间用 croniter 判断触发点，对每个启用了定时抓取的用户，
自动对关键词库中所有关键词执行 run_candidate_search。
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from croniter import croniter
from sqlalchemy import select
from zoneinfo import ZoneInfo

from app.db.session import SessionLocal
from app.models.pipeline_setting import PipelineSetting
from app.models.topic import Keyword
from app.services.candidate_service import run_candidate_search

logger = logging.getLogger("app.candidate_scheduler")

_TZ = ZoneInfo("Asia/Shanghai")
_POLL_INTERVAL_SECONDS = 60
_CONCURRENT_SEARCH_COUNT = 1

_scheduler_task: asyncio.Task | None = None
_scheduler_stop_event: asyncio.Event | None = None

# owner_id -> last_fire_key，避免同一触发点重复执行
_fired: dict[str, str] = {}


def start_candidate_scheduler() -> None:
    global _scheduler_task, _scheduler_stop_event
    if _scheduler_task is not None and not _scheduler_task.done():
        return
    _scheduler_stop_event = asyncio.Event()
    _scheduler_task = asyncio.get_running_loop().create_task(
        _start_scheduler_with_prefill(_scheduler_stop_event)
    )
    logger.info("【候选库调度器】已启动")


async def _start_scheduler_with_prefill(stop_event: asyncio.Event) -> None:
    """先预填 _fired 再进入调度循环，确保重启后不会立即重复执行。"""
    await _prefill_fired()
    await _scheduler_loop(stop_event)


async def _prefill_fired() -> None:
    """启动时预填 _fired，将当前已过的 cron 触发点标记为已执行，防止重启后立即触发。"""
    try:
        now_local = datetime.now(timezone.utc).astimezone(_TZ)
        async with SessionLocal() as session:
            result = await session.execute(
                select(PipelineSetting).where(PipelineSetting.candidate_schedule_enabled.is_(True))
            )
            settings_list = list(result.scalars().all())

        for ps in settings_list:
            cron_expr = (ps.candidate_schedule_cron or "").strip()
            if not cron_expr or not croniter.is_valid(cron_expr):
                continue
            cron = croniter(cron_expr, now_local, ret_type=datetime)
            prev_fire_local: datetime = cron.get_prev(datetime)
            _fired[str(ps.owner_id)] = prev_fire_local.strftime("%Y-%m-%d %H:%M")

        logger.info("【候选库调度器】预填 _fired 完成，共 %d 条", len(_fired))
    except Exception:
        logger.exception("【候选库调度器】预填 _fired 失败")


async def stop_candidate_scheduler() -> None:
    global _scheduler_task, _scheduler_stop_event
    stop_event, worker = _scheduler_stop_event, _scheduler_task
    _scheduler_stop_event = None
    _scheduler_task = None
    if stop_event:
        stop_event.set()
    if worker:
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass
    logger.info("【候选库调度器】已停止")


async def _scheduler_loop(stop_event: asyncio.Event) -> None:
    try:
        while not stop_event.is_set():
            try:
                await _run_once()
            except Exception:
                logger.exception("【候选库调度器】轮询异常")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=_POLL_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                continue
    except asyncio.CancelledError:
        raise


async def _run_once() -> None:
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(_TZ)

    async with SessionLocal() as session:
        result = await session.execute(
            select(PipelineSetting).where(PipelineSetting.candidate_schedule_enabled.is_(True))
        )
        settings_list: list[PipelineSetting] = list(result.scalars().all())

    if not settings_list:
        return

    for ps in settings_list:
        try:
            await _process_user(ps, now_utc=now_utc, now_local=now_local)
        except Exception:
            logger.exception("【候选库调度器】处理用户 %s 异常", ps.owner_id)


async def _process_user(ps: PipelineSetting, *, now_utc: datetime, now_local: datetime) -> None:
    cron_expr = (ps.candidate_schedule_cron or "").strip()
    if not cron_expr:
        return

    if not croniter.is_valid(cron_expr):
        logger.warning("【候选库调度器】用户 %s 的 Cron 表达式 %r 无效，跳过", ps.owner_id, cron_expr)
        return

    owner_id = ps.owner_id
    owner_key = str(owner_id)

    # 计算上一个 cron 触发点（北京时间）
    cron = croniter(cron_expr, now_local, ret_type=datetime)
    prev_fire_local: datetime = cron.get_prev(datetime)
    prev_fire_key = prev_fire_local.strftime("%Y-%m-%d %H:%M")
    prev_fire_utc = prev_fire_local.astimezone(timezone.utc)
    seconds_since_fire = (now_utc - prev_fire_utc).total_seconds()

    # 触发点必须在 poll 窗口内（0 ~ 90s）
    if seconds_since_fire < 0 or seconds_since_fire >= _POLL_INTERVAL_SECONDS * 1.5:
        return

    # 去重：同一触发点不重复执行
    if _fired.get(owner_key) == prev_fire_key:
        return
    _fired[owner_key] = prev_fire_key

    logger.info("【候选库调度器】触发用户 %s 的定时抓取（Cron=%s，触发点=%s）", owner_id, cron_expr, prev_fire_key)

    # 查询关键词库中该用户的所有关键词（admin 看全部）
    async with SessionLocal() as session:
        q = select(Keyword.id, Keyword.keyword)
        if owner_id is not None:
            q = q.where(Keyword.owner_id == owner_id)
        rows = (await session.execute(q)).all()
        keywords = [(r.id, r.keyword) for r in rows]

    if not keywords:
        logger.info("【候选库调度器】用户 %s 关键词库为空，跳过", owner_id)
        return

    total = len(keywords)
    logger.info("=" * 60)
    logger.info("【候选库调度器】用户 %s 开始定时抓取，共 %d 个关键词，最多 5 个并发", owner_id, total)
    logger.info("=" * 60)

    sem = asyncio.Semaphore(_CONCURRENT_SEARCH_COUNT)

    async def _process_keyword(idx: int, keyword_id: str, keyword_text: str) -> None:
        async with sem:
            logger.info("=========【候选库调度器】[%d/%d] 开始处理关键词「%s」(id=%s) =========", idx, total, keyword_text, keyword_id)
            try:
                async with SessionLocal() as session:
                    await run_candidate_search(
                        session=session,
                        keyword_text=keyword_text,
                        keyword_id=keyword_id,
                        owner_id=owner_id,
                    )
                logger.info("=========【候选库调度器】[%d/%d] 关键词「%s」搜索完成 =========", idx, total, keyword_text)
            except Exception:
                logger.exception("【候选库调度器】[%d/%d] 关键词「%s」搜索失败", idx, total, keyword_text)

    tasks = [
        asyncio.create_task(_process_keyword(idx, kid, ktxt))
        for idx, (kid, ktxt) in enumerate(keywords, 1)
    ]
    await asyncio.gather(*tasks)

    logger.info("=" * 60)
    logger.info("【候选库调度器】用户 %s 本轮定时抓取全部完成（%d 个关键词）", owner_id, total)
    logger.info("=" * 60)
