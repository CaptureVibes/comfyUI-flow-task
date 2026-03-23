"""
Account publish scheduler
=========================
每 60 秒轮询一次，对所有启用了定时发布的 AI 博主账号（Account.publish_enabled=True）：
1. 用 croniter 按北京时间判断上一个触发点是否在本轮 poll 窗口内
2. 用数据库字段 publish_last_triggered_at 去重（防止重启重复触发）
3. 若命中：随机延迟 0~publish_window_minutes 分钟后执行
4. 执行时从该账号的 queued 队列按 queue_order 取前 publish_count 个子任务，并发发布
5. 多账号之间并发处理（asyncio.gather）
"""
from __future__ import annotations

import asyncio
import logging
import random
import uuid
from datetime import datetime, timedelta, timezone

import pytz
from croniter import croniter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import SessionLocal
from app.models.account import Account
from app.models.video_task import VideoSubTask, VideoTask

logger = logging.getLogger("app.account_publish_scheduler")

_POLL_INTERVAL_SECONDS = 60.0
_TZ = pytz.timezone("Asia/Shanghai")

_scheduler_task: asyncio.Task | None = None
_scheduler_stop_event: asyncio.Event | None = None

# account_id -> (cron_fire_key, fire_at_utc)
_pending_fire: dict[uuid.UUID, tuple[str, datetime]] = {}


def start_account_publish_scheduler() -> None:
    global _scheduler_task, _scheduler_stop_event
    if _scheduler_task is not None and not _scheduler_task.done():
        return
    _scheduler_stop_event = asyncio.Event()
    _scheduler_task = asyncio.get_running_loop().create_task(
        _scheduler_loop(_scheduler_stop_event)
    )
    logger.info("【定时发布调度器】已启动，轮询间隔 %d 秒", int(_POLL_INTERVAL_SECONDS))


async def stop_account_publish_scheduler() -> None:
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
    logger.info("【定时发布调度器】已停止")


async def _scheduler_loop(stop_event: asyncio.Event) -> None:
    try:
        while not stop_event.is_set():
            try:
                await _run_once()
            except Exception:
                logger.exception("【定时发布调度器】轮询异常")
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
            select(Account).where(Account.publish_enabled.is_(True))
        )
        accounts: list[Account] = list(result.scalars().all())

    if not accounts:
        return

    logger.debug(
        "【定时发布调度器】轮询时间 %s（北京时间 %s），共 %d 个已启用账号",
        now_utc.strftime("%H:%M:%S UTC"),
        now_local.strftime("%H:%M:%S"),
        len(accounts),
    )

    # 多账号并发处理
    await asyncio.gather(
        *[_process_account(account, now_utc=now_utc, now_local=now_local) for account in accounts],
        return_exceptions=True,
    )


async def _process_account(account: Account, *, now_utc: datetime, now_local: datetime) -> None:
    cron_expr = (account.publish_cron or "").strip()
    if not cron_expr:
        return

    if not croniter.is_valid(cron_expr):
        logger.warning(
            "【定时发布】账号 %s（%s）的 Cron 表达式 %r 无效，跳过",
            account.id, account.account_name, cron_expr,
        )
        return

    account_id = account.id

    # ── 检查是否有待触发的延迟任务 ────────────────────────────────────────────
    if account_id in _pending_fire:
        fire_key, fire_at = _pending_fire[account_id]
        if now_utc >= fire_at:
            del _pending_fire[account_id]
            logger.info(
                "【定时发布】账号 %s（%s）随机延迟结束，开始发布（Cron触发点：%s，北京时间 %s）",
                account_id, account.account_name, fire_key,
                now_local.strftime("%H:%M:%S"),
            )
            await _do_publish(account)
        else:
            remaining = (fire_at - now_utc).total_seconds()
            logger.debug(
                "【定时发布】账号 %s（%s）等待随机延迟，剩余 %.0f 秒",
                account_id, account.account_name, remaining,
            )
        return

    # ── 计算上一个 cron 触发点（北京时间） ────────────────────────────────────
    cron = croniter(cron_expr, now_local, ret_type=datetime)
    prev_fire_local: datetime = cron.get_prev(datetime)
    prev_fire_key = prev_fire_local.strftime("%Y-%m-%d %H:%M")
    prev_fire_utc = prev_fire_local.astimezone(timezone.utc)
    seconds_since_fire = (now_utc - prev_fire_utc).total_seconds()

    logger.debug(
        "【定时发布】账号 %s（%s）Cron=%r，上次触发点=%s（%.0f 秒前）",
        account_id, account.account_name, cron_expr, prev_fire_key, seconds_since_fire,
    )

    # 触发点必须在 poll 窗口内（0 ~ 90s）
    if seconds_since_fire < 0 or seconds_since_fire >= _POLL_INTERVAL_SECONDS * 1.5:
        return

    # ── 数据库去重：上次触发时间是否已覆盖此触发点 ───────────────────────────
    if account.publish_last_triggered_at is not None:
        last = account.publish_last_triggered_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if last >= prev_fire_utc:
            logger.debug(
                "【定时发布】账号 %s（%s）触发点 %s 已发布过（上次触发：%s），跳过",
                account_id, account.account_name, prev_fire_key,
                last.strftime("%H:%M UTC"),
            )
            return

    logger.info(
        "【定时发布】账号 %s（%s）命中触发点 %s（北京时间），距触发 %.0f 秒，准备发布",
        account_id, account.account_name, prev_fire_key, seconds_since_fire,
    )

    # ── 写入 last_triggered_at（防止同一触发点重复安排）────────────────────
    async with SessionLocal() as session:
        acct = await session.get(Account, account_id)
        if acct is None:
            return
        acct.publish_last_triggered_at = now_utc
        await session.commit()
    account.publish_last_triggered_at = now_utc

    # ── 随机延迟 ─────────────────────────────────────────────────────────────
    window_minutes = account.publish_window_minutes or 0
    if window_minutes > 0:
        delay_seconds = random.randint(0, window_minutes * 60)
        fire_at = now_utc + timedelta(seconds=delay_seconds)
        _pending_fire[account_id] = (prev_fire_key, fire_at)
        logger.info(
            "【定时发布】账号 %s（%s）设置随机延迟 %d 秒（窗口 %d 分钟），将于 %s UTC 发布",
            account_id, account.account_name,
            delay_seconds, window_minutes,
            fire_at.strftime("%H:%M:%S"),
        )
    else:
        logger.info("【定时发布】账号 %s（%s）无随机延迟，立即开始发布", account_id, account.account_name)
        await _do_publish(account)


async def _do_publish(account: Account) -> None:
    """从队列取前 N 个 queued 子任务，按顺序串行发布"""
    publish_count = max(1, account.publish_count or 1)
    channels = _build_channels(account)

    if not channels:
        logger.warning(
            "【定时发布】账号 %s（%s）未配置发布渠道（social_bindings 为空），跳过",
            account.id, account.account_name,
        )
        return

    # 加载该账号 owner 的自动发布 AI 配置
    ai_config = await _load_auto_publish_config(account)

    async with SessionLocal() as session:
        result = await session.execute(
            select(VideoSubTask)
            .join(VideoTask, VideoSubTask.task_id == VideoTask.id)
            .where(
                VideoTask.account_id == account.id,
                VideoSubTask.status == "queued",
                VideoSubTask.result_video_url.isnot(None),
            )
            .order_by(VideoSubTask.queue_order.asc().nullslast())
            .limit(publish_count)
            .options(selectinload(VideoSubTask.task))
        )
        sub_tasks: list[VideoSubTask] = list(result.scalars().all())

    if not sub_tasks:
        logger.info("【定时发布】账号 %s（%s）发布队列为空，无需发布", account.id, account.account_name)
        return

    logger.info(
        "【定时发布】账号 %s（%s）准备发布 %d 个视频到 %d 个渠道",
        account.id, account.account_name, len(sub_tasks), len(channels),
    )

    # 同一账号内按 queue_order 串行发布，保证顺序
    for sub in sub_tasks:
        try:
            await _publish_sub_task(sub.id, channels, account.account_name, ai_config)
        except Exception:
            logger.exception(
                "【定时发布】账号 %s（%s）发布子任务 %s 失败，继续下一个",
                account.id, account.account_name, sub.id,
            )


async def _load_auto_publish_config(account: Account) -> dict | None:
    """加载账号 owner 的自动发布 AI 配置，若未启用返回 None"""
    from app.models.video_task_config import VideoTaskConfig
    from app.services.system_settings_service import get_or_create_system_settings

    # 查 owner_id：从账号的 owner_id 找到对应的 VideoTaskConfig
    owner_id = account.owner_id
    if owner_id is None:
        # admin 账号没有 owner_id，尝试找任意一个 config
        return None

    async with SessionLocal() as session:
        cfg = await session.get(VideoTaskConfig, owner_id)
        if cfg is None or not cfg.auto_publish_enabled:
            return None
        if not cfg.auto_publish_prompt.strip():
            logger.warning("【定时发布】账号 %s（%s）已启用 AI 生成标题，但提示词为空，跳过 AI 生成", account.id, account.account_name)
            return None

        sys_cfg = await get_or_create_system_settings(session)
        api_key = getattr(sys_cfg, "evolink_api_key", "") or ""
        api_base_url = getattr(sys_cfg, "evolink_api_base_url", "") or ""

        if not api_key or not api_base_url:
            logger.warning("【定时发布】账号 %s（%s）已启用 AI 生成标题，但 EvoLink 未配置 api_key 或 api_base_url，跳过 AI 生成", account.id, account.account_name)
            return None

        return {
            "model": cfg.auto_publish_model or "gemini-2.0-flash",
            "prompt": cfg.auto_publish_prompt,
            "api_key": api_key,
            "api_base_url": api_base_url,
        }


async def _generate_publish_metadata(
    video_url: str,
    ai_config: dict,
    fallback_title: str,
) -> tuple[str, str, list[str]]:
    """
    调用 EvoLink AI 分析视频，生成 title/desc/hashtag。
    返回 (title, description, hashtags)。失败时返回 fallback。
    """
    import json as _json
    import re
    from app.services.evolink_api import call_evolink_gemini_api

    user_prompt = ai_config["prompt"].strip()
    prompt = f"""{user_prompt}

---
请严格按照以下 JSON 格式输出，不要输出任何其他内容，不要有 markdown 代码块包裹：
{{
  "title": "视频标题（简洁吸引人，不超过100字符）",
  "desc": "视频描述（详细介绍视频内容，可适当使用 emoji）",
  "hashtag": ["标签1", "标签2", "标签3"]
}}
其中 hashtag 为字符串数组，每个元素不含 # 号。只输出 JSON，不要任何解释。"""
    try:
        raw = await call_evolink_gemini_api(
            api_base_url=ai_config["api_base_url"],
            api_key=ai_config["api_key"],
            model_name=ai_config["model"],
            video_url=video_url,
            prompt=prompt,
            temperature=0.5,
        )
        logger.info("【AI生成标题】原始响应：%s", raw[:1000])

        # 提取 JSON（兼容 markdown 代码块包裹）
        json_str = raw.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", json_str)
        if match:
            logger.debug("【AI生成标题】检测到 markdown 代码块，提取 JSON 内容")
            json_str = match.group(1)

        data = _json.loads(json_str)
        title = str(data.get("title", "") or fallback_title)[:100]
        desc = str(data.get("desc", "") or data.get("description", "") or "")
        hashtags_raw = data.get("hashtag", data.get("hashtags", []))
        if isinstance(hashtags_raw, str):
            hashtags = [t.strip().lstrip("#") for t in hashtags_raw.split() if t.strip()]
        else:
            hashtags = [str(t).strip().lstrip("#") for t in hashtags_raw if t]

        logger.info(
            "【AI生成标题】生成成功 → 标题：%r，描述长度：%d 字，标签：%s",
            title, len(desc), hashtags,
        )
        return title, desc, hashtags

    except Exception as e:
        logger.error("【AI生成标题】生成失败：%s，使用兜底标题：%r", e, fallback_title)
        return fallback_title, "", []


async def _publish_sub_task(
    sub_task_id: uuid.UUID,
    channels: list[dict],
    account_name: str,
    ai_config: dict | None,
) -> None:
    from app.services.video_publication_service import VideoPublicationService
    from app.schemas.video_publication import VideoPublicationCreate

    async with SessionLocal() as session:
        result = await session.execute(
            select(VideoSubTask)
            .where(VideoSubTask.id == sub_task_id)
            .options(selectinload(VideoSubTask.task))
        )
        sub = result.scalar_one_or_none()
        if sub is None:
            logger.warning("【定时发布】子任务 %s 不存在，跳过", sub_task_id)
            return
        if sub.status != "queued":
            logger.info("【定时发布】子任务 %s 状态为 %s（已不在队列），跳过", sub_task_id, sub.status)
            return
        if not sub.result_video_url:
            logger.warning("【定时发布】子任务 %s 无视频地址，跳过", sub_task_id)
            return

        task = sub.task
        fallback_title = (task.prompt or "")[:100] or "视频"

    # ── AI 生成 title/desc/hashtag（在 session 外执行，避免长时间持有连接）──
    if ai_config:
        title, description, hashtags = await _generate_publish_metadata(
            video_url=sub.result_video_url,
            ai_config=ai_config,
            fallback_title=fallback_title,
        )
    else:
        title, description, hashtags = fallback_title, "", []

    # ── 发布 ──────────────────────────────────────────────────────────────────
    async with SessionLocal() as session:
        result = await session.execute(
            select(VideoSubTask)
            .where(VideoSubTask.id == sub_task_id)
            .options(selectinload(VideoSubTask.task))
        )
        sub = result.scalar_one_or_none()
        if sub is None or sub.status != "queued":
            return

        task = sub.task
        service = VideoPublicationService(session)
        try:
            await service.create_publication(VideoPublicationCreate(
                sub_task_id=sub.id,
                video_url=sub.result_video_url,
                title=title,
                description=description or None,
                tags=hashtags or None,
                channels=channels,
            ))
            sub.status = "publishing"
            sub.queue_order = None
            task.status = "publishing"
            await session.commit()
            logger.info(
                "【定时发布】子任务 %s（账号：%s）已提交发布 → publishing（标题：%r）",
                sub_task_id, account_name, title,
            )
        except Exception as e:
            logger.error(
                "【定时发布】子任务 %s（账号：%s）发布失败：%s",
                sub_task_id, account_name, e,
            )
            raise


def _build_channels(account: Account) -> list[dict]:
    bindings = account.social_bindings or []
    return [
        {"platform": b.get("platform", ""), "channel_id": b["channel_id"]}
        for b in bindings
        if isinstance(b, dict) and b.get("channel_id")
    ]
