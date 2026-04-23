"""
publish_meta_service.py
=======================
负责在视频子任务进入发布队列时，异步预生成 AI 标题/描述/标签，
并将结果写入 video_sub_tasks.publish_meta。

publish_meta 字段格式：
{
    "status": "pending" | "generating" | "done" | "failed",
    "title": "...",
    "description": "...",
    "hashtags": ["tag1", "tag2"]
}

队列设计：
- 全局 asyncio.Queue 串行接收任务，3 个 worker 并发消费
- enqueue_publish_meta_task() 将 sub_task_id 放入队列，同时把 publish_meta 写为 pending
- recover 时将 generating 状态的任务优先插入队列头部（通过优先队列实现）
"""
from __future__ import annotations

import asyncio
import json as _json
import logging
import uuid
from collections import deque

from app.db.session import SessionLocal
from app.models.video_task import VideoSubTask, VideoTask

logger = logging.getLogger("app.publish_meta_service")

# ── 全局队列与 worker ──────────────────────────────────────────────────────────
# 使用 deque 实现支持 appendleft（优先插入头部）的队列，配合 asyncio.Event 通知
_task_deque: deque[uuid.UUID] = deque()
_task_event: asyncio.Event | None = None   # 延迟初始化，须在 event loop 内创建
_WORKER_COUNT = 3
_workers: list[asyncio.Task] = []


def _get_event() -> asyncio.Event:
    global _task_event
    if _task_event is None:
        _task_event = asyncio.Event()
    return _task_event


async def _worker(worker_id: int) -> None:
    """持续从 _task_deque 取任务并执行，并发数由 worker 数量控制。"""
    event = _get_event()
    logger.info("【AI预生成标题】worker-%d 启动", worker_id)
    while True:
        # 等待有任务
        await event.wait()
        try:
            sub_task_id = _task_deque.popleft()
        except IndexError:
            # 被其他 worker 抢先取走了，清除 event 重新等待
            event.clear()
            continue
        # 队列还有任务则保持 event set
        if not _task_deque:
            event.clear()

        try:
            await _process_publish_meta(sub_task_id)
        except Exception:
            logger.exception("【AI预生成标题】worker-%d 处理子任务 %s 异常", worker_id, sub_task_id)


def enqueue_publish_meta_task(sub_task_id: uuid.UUID, *, priority: bool = False) -> None:
    """将 sub_task_id 加入生成队列。priority=True 时插入头部（用于 recover）。"""
    if priority:
        _task_deque.appendleft(sub_task_id)
    else:
        _task_deque.append(sub_task_id)
    _get_event().set()


async def start_publish_meta_workers() -> None:
    """在应用启动时调用，启动 _WORKER_COUNT 个后台 worker。"""
    global _workers
    _get_event()  # 确保在 event loop 内初始化
    _workers = [
        asyncio.create_task(_worker(i + 1), name=f"publish-meta-worker-{i + 1}")
        for i in range(_WORKER_COUNT)
    ]
    logger.info("【AI预生成标题】已启动 %d 个 worker", _WORKER_COUNT)


async def stop_publish_meta_workers() -> None:
    """在应用关闭时调用，取消所有 worker。"""
    for w in _workers:
        w.cancel()
    await asyncio.gather(*_workers, return_exceptions=True)
    _workers.clear()
    logger.info("【AI预生成标题】所有 worker 已停止")


# ── 配置加载 ───────────────────────────────────────────────────────────────────

async def _load_auto_publish_config(owner_id: uuid.UUID | None) -> dict | None:
    """加载 owner 的自动发布 AI 配置，若未启用返回 None。"""
    from app.models.video_task_config import VideoTaskConfig
    from app.services.google_api import get_google_api_key

    if owner_id is None:
        return None

    async with SessionLocal() as session:
        cfg = await session.get(VideoTaskConfig, owner_id)
        if cfg is None:
            return None
        if not (cfg.auto_publish_prompt or "").strip():
            logger.warning("owner %s 未配置 AI 生成标题提示词", owner_id)
            return None

        api_key = get_google_api_key()
        if not api_key:
            logger.warning("owner %s 已启用 AI 生成标题，但 GOOGLE_API_KEY 未配置", owner_id)
            return None

        return {
            "model": cfg.auto_publish_model or "gemini-2.0-flash",
            "prompt": cfg.auto_publish_prompt,
        }


# ── AI 生成逻辑 ────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """
You are an expert YouTube Shorts copywriter for North American audiences.
I will provide a text description of a video. Based on that description, generate the following 3 items for a YouTube Shorts post:

Title
Description
Hashtags
Follow these rules exactly:
Title

Use English
Keep it as short as possible, ideally 10 to 30 characters
Plain text only
No emojis
No special symbols
Prefer a question format, since questions usually attract more views
Start with a strong hook when possible, such as: THIS, Stop, Try, Which, This or That
Match North American audience preferences
Make it catchy and suitable for YouTube Shorts
Description

Use English
Maximum 20 words
Keep it short and natural
Match North American audience preferences
Highlight the main appeal of the video
Do not sound too wordy or promotional
Hashtags

Generate 3 to 5 English hashtags
Do not exceed 5 hashtags
Make them highly relevant to the video content
Prioritize the most suitable tags from this list when relevant:
#fashion #ootd #outfit #style #stunningoutfit #outfittrend #streetfashionoutfit #fashionhacks

Here is the video description:
"""

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "title":   {"type": "string"},
        "desc":    {"type": "string"},
        "hashtag": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "desc", "hashtag"],
}


async def generate_publish_metadata(
    video_prompt: str,
    ai_config: dict,
    fallback_title: str,
) -> tuple[str, str, list[str]]:
    """
    根据视频描述文本调用 Gemini API，生成 title/description/hashtags。
    返回 (title, description, hashtags)。失败时有限重试。
    """
    from app.services.ai_api import call_gemini_api

    prompt = f"{_SYSTEM_PROMPT}\n{video_prompt.strip()}"

    FALLBACK_MODEL = "gemini-2.5-flash"
    PRIMARY_MAX = 3
    FALLBACK_MAX = 3
    retry_delay = 30.0

    models = [
        (ai_config["model"], PRIMARY_MAX),
        (FALLBACK_MODEL, FALLBACK_MAX),
    ]

    for model_name, max_attempts in models:
        attempt = 0
        while attempt < max_attempts:
            attempt += 1
            logger.info("【AI预生成标题】第%d次调用 Gemini API，模型: %s", attempt, model_name)
            try:
                raw = await call_gemini_api(
                    model_name=model_name,
                    prompt=prompt,
                    temperature=0.5,
                    response_schema=_RESPONSE_SCHEMA,
                )
                logger.info("【AI预生成标题】原始响应（第%d次）：%s", attempt, raw[:500])

                data = _json.loads(raw)
                title = str(data.get("title", "") or "").strip()[:100]
                if not title:
                    raise ValueError("AI 返回的 JSON 缺少有效 title 字段")
                desc = str(data.get("desc", "") or "")
                hashtags = [str(t).strip().lstrip("#") for t in data.get("hashtag", []) if t]

                logger.info("【AI预生成标题】成功（第%d次，模型: %s） → %r", attempt, model_name, title)
                return title, desc, hashtags

            except Exception as e:
                exc_str = str(e)
                # 4xx 错误跳出当前模型直接换下一个
                is_4xx = any(code in exc_str for code in ["400", "401", "403", "404"])
                if is_4xx:
                    logger.warning("【AI预生成标题】模型 %s 4xx 错误，换模型重试：%s", model_name, exc_str[:300])
                    break
                if attempt >= max_attempts:
                    logger.warning("【AI预生成标题】模型 %s 已达最大重试次数 %d，换模型重试", model_name, max_attempts)
                    break
                logger.warning("【AI预生成标题】第%d次失败（模型: %s）：%s，%.0fs后重试", attempt, model_name, exc_str[:300], retry_delay)
                await asyncio.sleep(retry_delay)

    raise RuntimeError("AI 生成标题失败：主模型和备用模型均已耗尽重试次数")


async def _process_publish_meta(sub_task_id: uuid.UUID) -> None:
    """worker 实际执行的处理逻辑：读取子任务 → 标记 generating → AI 生成 → 写回结果。"""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    # 1. 读取子任务信息
    async with SessionLocal() as session:
        row = await session.execute(
            select(VideoSubTask)
            .where(VideoSubTask.id == sub_task_id)
            .options(selectinload(VideoSubTask.task))
        )
        sub = row.scalar_one_or_none()
        if sub is None:
            return
        # 已被手动重新生成完成，跳过
        if (sub.publish_meta or {}).get("status") == "done":
            logger.info("【AI预生成标题】子任务 %s 已完成，跳过", sub_task_id)
            return

        video_prompt = (sub.task.prompt or "").strip()
        owner_id = sub.task.owner_id
        fallback_title = video_prompt[:100] or "视频"

    if not video_prompt:
        logger.info("【AI预生成标题】子任务 %s 的 task.prompt 为空，跳过", sub_task_id)
        async with SessionLocal() as session:
            sub = await session.get(VideoSubTask, sub_task_id)
            if sub is not None:
                sub.publish_meta = {"status": "failed"}
                await session.commit()
        return

    # 2. 加载 AI 配置
    ai_config = await _load_auto_publish_config(owner_id)
    if ai_config is None:
        logger.info("【AI预生成标题】子任务 %s owner 未启用 AI 生成标题，跳过", sub_task_id)
        return

    # 3. 标记为 generating
    async with SessionLocal() as session:
        sub = await session.get(VideoSubTask, sub_task_id)
        if sub is None:
            return
        sub.publish_meta = {"status": "generating"}
        await session.commit()

    logger.info("【AI预生成标题】子任务 %s 开始生成标题，prompt 前50字: %s", sub_task_id, video_prompt[:50])

    # 4. 调用 AI 生成
    try:
        title, description, hashtags = await generate_publish_metadata(
            video_prompt=video_prompt,
            ai_config=ai_config,
            fallback_title=fallback_title,
        )
        meta = {
            "status": "done",
            "title": title,
            "description": description,
            "hashtags": hashtags,
        }
    except Exception as e:
        logger.error("【AI预生成标题】子任务 %s 生成失败：%s", sub_task_id, e)
        meta = {"status": "failed"}

    # 5. 写回 DB
    async with SessionLocal() as session:
        sub = await session.get(VideoSubTask, sub_task_id)
        if sub is None:
            return
        sub.publish_meta = meta
        await session.commit()

    logger.info("【AI预生成标题】子任务 %s 完成，状态: %s", sub_task_id, meta["status"])


# ── 启动恢复 ───────────────────────────────────────────────────────────────────

async def recover_stuck_publish_meta_on_startup() -> None:
    """
    启动时补跑未完成的标题生成任务：
    - generating 状态：插入队列头部（优先处理）
    - pending 状态：插入队列尾部
    """
    from sqlalchemy import select, or_

    async with SessionLocal() as session:
        # generating 优先
        generating_ids = (await session.execute(
            select(VideoSubTask.id).where(
                VideoSubTask.publish_meta["status"].as_string() == "generating",
                VideoSubTask.status == "queued",
            )
        )).scalars().all()

        pending_ids = (await session.execute(
            select(VideoSubTask.id).where(
                VideoSubTask.status == "queued",
                or_(
                    VideoSubTask.publish_meta.is_(None),
                    VideoSubTask.publish_meta["status"].as_string() == "pending",
                ),
            )
        )).scalars().all()

    if not generating_ids and not pending_ids:
        return

    logger.info(
        "【AI预生成标题】启动补跑：generating=%d，pending/null=%d",
        len(generating_ids), len(pending_ids),
    )

    # generating 插队列头部（逆序 appendleft 保持原顺序）
    for sub_task_id in reversed(generating_ids):
        enqueue_publish_meta_task(sub_task_id, priority=True)

    for sub_task_id in pending_ids:
        enqueue_publish_meta_task(sub_task_id)
