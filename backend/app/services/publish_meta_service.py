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
"""
from __future__ import annotations

import json as _json
import logging
import re
import uuid

from app.db.session import SessionLocal
from app.models.video_task import VideoSubTask, VideoTask

logger = logging.getLogger("app.publish_meta_service")


async def _load_auto_publish_config(owner_id: uuid.UUID | None) -> dict | None:
    """加载 owner 的自动发布 AI 配置，若未启用返回 None。"""
    from app.models.video_task_config import VideoTaskConfig
    from app.services.google_api import get_google_api_key

    if owner_id is None:
        return None

    async with SessionLocal() as session:
        cfg = await session.get(VideoTaskConfig, owner_id)
        if cfg is None or not cfg.auto_publish_enabled:
            return None
        if not (cfg.auto_publish_prompt or "").strip():
            logger.warning("owner %s 已启用 AI 生成标题，但提示词为空", owner_id)
            return None

        api_key = get_google_api_key()
        if not api_key:
            logger.warning("owner %s 已启用 AI 生成标题，但 GOOGLE_API_KEY 未配置", owner_id)
            return None

        return {
            "model": cfg.auto_publish_model or "gemini-2.0-flash",
            "prompt": cfg.auto_publish_prompt,
        }


async def generate_publish_metadata(
    video_url: str,
    ai_config: dict,
    fallback_title: str,
) -> tuple[str, str, list[str]]:
    """
    调用 Gemini API 分析视频，生成 title/description/hashtags。
    返回 (title, description, hashtags)。失败时无限重试。
    """
    import asyncio
    from app.services.ai_api import call_gemini_api

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

    retry_delay = 30.0
    attempt = 0
    while True:
        attempt += 1
        logger.info("【AI预生成标题】第%d次调用 Gemini API，模型: %s", attempt, ai_config["model"])
        try:
            raw = await call_gemini_api(
                model_name=ai_config["model"],
                video_url=video_url,
                prompt=prompt,
                temperature=0.5,
            )
            logger.info("【AI预生成标题】原始响应（第%d次）：%s", attempt, raw[:500])

            json_str = raw.strip()
            match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", json_str)
            if match:
                json_str = match.group(1)

            data = _json.loads(json_str)
            title = str(data.get("title", "") or "").strip()
            if not title:
                raise ValueError("AI 返回的 JSON 缺少有效 title 字段")

            title = title[:100]
            desc = str(data.get("desc", "") or data.get("description", "") or "")
            hashtags_raw = data.get("hashtag", data.get("hashtags", []))
            if isinstance(hashtags_raw, str):
                hashtags = [t.strip().lstrip("#") for t in hashtags_raw.split() if t.strip()]
            else:
                hashtags = [str(t).strip().lstrip("#") for t in hashtags_raw if t]

            logger.info("【AI预生成标题】成功（第%d次） → %r", attempt, title)
            return title, desc, hashtags

        except Exception as e:
            logger.warning("【AI预生成标题】第%d次失败：%s，%.0fs后重试", attempt, e, retry_delay)
            await asyncio.sleep(retry_delay)


async def trigger_publish_meta_generation(sub_task_id: uuid.UUID) -> None:
    """
    后台任务：为刚进入 queued 的子任务预生成发布标题。
    由 enqueue_sub_task 在 commit 后以 asyncio.create_task 调用。
    """
    import asyncio

    # 1. 读取子任务信息
    async with SessionLocal() as session:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        row = await session.execute(
            select(VideoSubTask)
            .where(VideoSubTask.id == sub_task_id)
            .options(selectinload(VideoSubTask.task))
        )
        sub = row.scalar_one_or_none()
        if sub is None:
            return

        video_url = sub.result_video_url
        owner_id = sub.task.owner_id
        fallback_title = (sub.task.prompt or "")[:100] or "视频"
        account_id = sub.task.account_id

    if not video_url:
        logger.info("【AI预生成标题】子任务 %s 无视频 URL，跳过", sub_task_id)
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

    logger.info("【AI预生成标题】子任务 %s 开始生成标题，视频: %s", sub_task_id, video_url[:80])

    # 4. 调用 AI 生成
    try:
        title, description, hashtags = await generate_publish_metadata(
            video_url=video_url,
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
        # 仍在队列才写回（防止已出队）
        sub.publish_meta = meta
        await session.commit()

    logger.info("【AI预生成标题】子任务 %s 完成，状态: %s", sub_task_id, meta["status"])
