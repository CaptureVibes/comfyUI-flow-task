from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

import httpx

from app.db.session import SessionLocal
from app.models.enums import VideoAIProcessStatus
from app.models.video_ai_template import VideoAITemplate

logger = logging.getLogger("app.video_ai")

# =============================================================================
# 全局变量
# =============================================================================

# video_ai_states: 存储模板的内存状态 {template_id: state_dict}
# dirty_video_ai_ids: 需要持久化到数据库的模板 ID 集合
# video_ai_worker_tasks: 正在运行的任务 {template_id: asyncio.Task}
# video_ai_queue: 任务队列，存储待处理的模板 ID
video_ai_states: dict[str, dict] = {}
dirty_video_ai_ids: set[str] = set()
video_ai_worker_tasks: dict[str, asyncio.Task] = {}
video_ai_queue: asyncio.Queue[str] = asyncio.Queue()

# 队列处理器任务和持久化任务
_queue_processor_task: asyncio.Task | None = None
_persist_worker_task: asyncio.Task | None = None

# 并发数：同时处理的最大任务数
_CONCURRENCY = 3
# 持久化间隔：每 2 秒持久化一次脏数据到数据库
_PERSIST_INTERVAL = 2.0


def _utcnow_iso() -> str:
    """获取当前 UTC 时间并格式化为 ISO 字符串"""
    return datetime.now(timezone.utc).isoformat()


# =============================================================================
# 状态管理辅助函数
# =============================================================================


def _new_state(template_id: str, status: VideoAIProcessStatus) -> dict:
    """
    创建新的状态字典

    Args:
        template_id: 模板 ID
        status: 初始状态

    Returns:
        状态字典
    """
    return {
        "template_id": template_id,
        "status": status.value,
        "error_message": "",
        "prompt_description": "",
        "extracted_shots": [],
        "updated_at": _utcnow_iso(),
    }


def _mark_dirty(template_id: str) -> None:
    """
    标记模板为脏状态，需要持久化到数据库

    Args:
        template_id: 模板 ID
    """
    dirty_video_ai_ids.add(template_id)


def _set_status(template_id: str, status: VideoAIProcessStatus, *, error: str = "") -> None:
    """
    设置模板状态

    Args:
        template_id: 模板 ID
        status: 新状态
        error: 错误信息（可选）
    """
    state = video_ai_states.setdefault(template_id, _new_state(template_id, status))
    state["status"] = status.value
    state["error_message"] = error
    state["updated_at"] = _utcnow_iso()
    _mark_dirty(template_id)


# =============================================================================
# 数据库持久化
# =============================================================================


async def _persist_states(template_ids: list[str]) -> None:
    """
    将内存状态持久化到数据库

    Args:
        template_ids: 需要持久化的模板 ID 列表
    """
    if not template_ids:
        return
    async with SessionLocal() as session:
        for tid in template_ids:
            state = video_ai_states.get(tid)
            if state is None:
                continue
            try:
                uuid_val = UUID(tid)
            except ValueError:
                continue
            tpl = await session.get(VideoAITemplate, uuid_val)
            if not tpl:
                continue
            # 更新数据库字段
            tpl.process_status = VideoAIProcessStatus(state["status"])
            tpl.process_error = state.get("error_message") or None
            # 如果有新的 prompt_description，才更新
            if state.get("prompt_description"):
                tpl.prompt_description = state.get("prompt_description")
            # 如果有新的 extracted_shots，才更新
            extracted = state.get("extracted_shots")
            if extracted is not None:
                tpl.extracted_shots = extracted
            # 保存完整状态 JSON
            tpl.process_state = json.dumps(state, ensure_ascii=False)
        await session.commit()


async def _persist_worker_loop() -> None:
    """
    持久化工作循环，定期将脏数据写入数据库
    """
    global _persist_worker_task
    try:
        while True:
            await asyncio.sleep(_PERSIST_INTERVAL)
            ids = list(dirty_video_ai_ids)
            if not ids:
                continue
            dirty_video_ai_ids.difference_update(ids)
            await _persist_states(ids)
    except asyncio.CancelledError:
        # 退出前保存剩余数据
        ids = list(dirty_video_ai_ids)
        if ids:
            dirty_video_ai_ids.difference_update(ids)
            await _persist_states(ids)
        raise
    except Exception:
        logger.exception("Video AI persist worker crashed")


def _ensure_persist_worker() -> None:
    """
    确保持久化工作线程正在运行
    """
    global _persist_worker_task
    if _persist_worker_task is not None and not _persist_worker_task.done():
        return
    loop = asyncio.get_running_loop()
    _persist_worker_task = loop.create_task(_persist_worker_loop())


# =============================================================================
# EvoLink API 调用
# =============================================================================


async def _call_evolink_api(
    *,
    api_base_url: str,
    api_key: str,
    model_name: str,
    video_url: str,
    prompt: str,
    temperature: float = 0.3,
) -> str:
    """
    调用 EvoLink API (Gemini 协议) 进行视频分析

    Args:
        api_base_url: API 基础 URL
        api_key: API 密钥
        model_name: 模型名称（如 gemini-2.5-flash）
        video_url: 视频 URL（必须是公网可访问的）
        prompt: 提示词
        temperature: 生成温度（0-2）

    Returns:
        AI 返回的文本内容

    Raises:
        ValueError: 响应格式错误
        httpx.HTTPStatusError: HTTP 请求失败
    """
    # 构建请求 URL 和 payload
    url = f"{api_base_url.rstrip('/')}/v1beta/models/{model_name}:generateContent"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"fileData": {"mimeType": "video/mp4", "fileUri": video_url}},
                    {"text": prompt},
                ],
            }
        ],
        "generationConfig": {"temperature": temperature},
    }

    # 记录请求日志（隐藏 API 密钥）
    masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
    logger.info("EvoLink API request: url=%s, model=%s, api_key=%s, temperature=%s", url, model_name, masked_key, temperature)
    logger.info("EvoLink API request: video_url=%s", video_url)
    logger.info("EvoLink API request: prompt=%s", prompt[:400] if len(prompt) > 400 else prompt)
    logger.debug("EvoLink API request: payload=%s", payload)

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        if not resp.is_success:
            logger.error("EvoLink API error: status=%d, response=%s", resp.status_code, resp.text)
        resp.raise_for_status()
        data = resp.json()

    # 记录原始响应（用于调试）
    logger.info("EvoLink API raw response: %s", json.dumps(data, ensure_ascii=False)[:1000])

    # 从 Gemini 风格的响应中提取文本
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        logger.info("EvoLink API extracted text: %s", text[:500] if len(text) > 500 else text)
        return text
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"Unexpected EvoLink response format: {data}") from exc


# =============================================================================
# 处理管道（Pipeline）
# =============================================================================


async def _run_pipeline(template_id: str, semaphore: asyncio.Semaphore) -> None:
    """
    执行视频 AI 处理管道

    流程：理解 → 提取 → 下载 → 上传 → 成功/失败

    Args:
        template_id: 模板 ID
        semaphore: 并发控制信号量
    """
    async with semaphore:
        # 从数据库加载模板和设置
        async with SessionLocal() as session:
            try:
                uuid_val = UUID(template_id)
            except ValueError:
                return
            tpl = await session.get(VideoAITemplate, uuid_val)
            if not tpl:
                logger.warning("VideoAITemplate %s not found", template_id)
                return

            # 加载视频源 URL - 优先使用 local_video_url（CDN），而非 video_url（原始平台）
            video_url: str | None = None
            if tpl.video_source_id:
                from app.models.video_source import VideoSource
                vs = await session.get(VideoSource, tpl.video_source_id)
                if vs:
                    # 检查下载状态
                    if vs.download_status == 'downloading':
                        logger.info("[%s] Video is still downloading, will retry later", template_id)
                        _set_status(template_id, VideoAIProcessStatus.fail, error="视频正在下载中，请稍后重试")
                        await _persist_states([template_id])
                        return
                    elif vs.download_status == 'failed':
                        logger.warning("[%s] Video download failed", template_id)
                        _set_status(template_id, VideoAIProcessStatus.fail, error="视频下载失败")
                        await _persist_states([template_id])
                        return

                    # 优先使用 local_video_url（已上传到 CDN），回退到原始 video_url
                    if vs.local_video_url:
                        video_url = vs.local_video_url
                        logger.info("[%s] Using local_video_url (CDN): %s", template_id, video_url[:100] + "...")
                    elif vs.video_url:
                        video_url = vs.video_url
                        logger.warning("[%s] Using original video_url (platform) - may not work with Gemini: %s", template_id, video_url[:100] + "...")

            if not video_url:
                logger.warning("[%s] No video URL available", template_id)
                _set_status(template_id, VideoAIProcessStatus.fail, error="视频地址不可用")
                await _persist_states([template_id])
                return

            # 加载系统配置（api_key/url）和用户流程配置（understand_*）
            from app.services.system_settings_service import get_or_create_system_settings
            from app.services.pipeline_settings_service import get_or_create_pipeline_settings
            sys_cfg = await get_or_create_system_settings(session)
            api_key = sys_cfg.evolink_api_key
            api_base_url = sys_cfg.evolink_api_base_url
            # 步骤一：视频整体理解（如模板无 owner_id 则使用默认配置）
            if tpl.owner_id is not None:
                pipeline_cfg = await get_or_create_pipeline_settings(session, owner_id=tpl.owner_id)
                understand_model = pipeline_cfg.understand_model or "gemini-3.1-pro-preview"
                understand_prompt = pipeline_cfg.understand_prompt or "请描述这个视频的内容，包括场景、人物、服装风格等。"
                understand_temperature = pipeline_cfg.understand_temperature
            else:
                understand_model = "gemini-3.1-pro-preview"
                understand_prompt = "请描述这个视频的内容，包括场景、人物、服装风格等。"
                understand_temperature = 0.3
        try:
            # ========== 步骤 1: 视频整体理解 ==========
            _set_status(template_id, VideoAIProcessStatus.understanding)
            logger.info("[%s] understanding started", template_id)

            prompt_description = ""
            if not video_url:
                raise ValueError("视频地址不可用，请确保已选择有效的视频源。")
            if not api_key:
                raise ValueError("系统未配置 EvoLink API Key，请前往【系统设置】进行配置。")
                
            prompt_description = await _call_evolink_api(
                api_base_url=api_base_url,
                api_key=api_key,
                model_name=understand_model,
                video_url=video_url,
                prompt=understand_prompt,
                temperature=understand_temperature,
            )
            state = video_ai_states.setdefault(template_id, _new_state(template_id, VideoAIProcessStatus.understanding))
            state["prompt_description"] = prompt_description
            state["updated_at"] = _utcnow_iso()
            _mark_dirty(template_id)

            # 立即持久化 prompt_description 到数据库
            async with SessionLocal() as session:
                tpl = await session.get(VideoAITemplate, uuid_val)
                if tpl:
                    tpl.prompt_description = prompt_description
                    await session.commit()

            # ========== 步骤 2: 成功 ==========
            _set_status(template_id, VideoAIProcessStatus.success)
            logger.info("[%s] pipeline completed", template_id)

            # 最终持久化
            await _persist_states([template_id])

        except asyncio.CancelledError:
            # 任务被取消，标记为暂停
            _set_status(template_id, VideoAIProcessStatus.paused)
            await _persist_states([template_id])
            raise
        except Exception as exc:
            # 任务失败，记录错误
            logger.exception("[%s] pipeline failed: %s", template_id, exc)
            _set_status(template_id, VideoAIProcessStatus.fail, error=str(exc))
            await _persist_states([template_id])
        finally:
            # 清理任务引用
            video_ai_worker_tasks.pop(template_id, None)


# =============================================================================
# 队列处理器
# =============================================================================


async def _queue_processor_loop() -> None:
    """
    队列处理循环，从队列中获取任务并执行
    """
    semaphore = asyncio.Semaphore(_CONCURRENCY)
    while True:
        try:
            template_id = await video_ai_queue.get()
            task = asyncio.get_running_loop().create_task(_run_pipeline(template_id, semaphore))
            video_ai_worker_tasks[template_id] = task
            video_ai_queue.task_done()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Video AI queue processor error, continuing")


# =============================================================================
# 公共 API
# =============================================================================


async def enqueue_template(template_id: str) -> None:
    """
    将模板加入队列并标记为等待中

    Args:
        template_id: 模板 ID
    """
    _set_status(template_id, VideoAIProcessStatus.pending)
    _ensure_persist_worker()
    # 立即持久化状态
    await _persist_states([template_id])
    dirty_video_ai_ids.discard(template_id)
    await video_ai_queue.put(template_id)
    logger.info("[%s] enqueued", template_id)


async def pause_template(template_id: str) -> None:
    """
    暂停正在运行的任务并标记为已暂停

    Args:
        template_id: 模板 ID
    """
    task = video_ai_worker_tasks.get(template_id)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    _set_status(template_id, VideoAIProcessStatus.paused)
    await _persist_states([template_id])
    dirty_video_ai_ids.discard(template_id)
    logger.info("[%s] paused", template_id)


async def resume_template(template_id: str) -> None:
    """
    恢复暂停或失败的模板

    Args:
        template_id: 模板 ID
    """
    await enqueue_template(template_id)


def get_template_state(template_id: str) -> dict | None:
    """
    获取模板的内存状态

    Args:
        template_id: 模板 ID

    Returns:
        状态字典，如果不存在返回 None
    """
    return video_ai_states.get(template_id)


# =============================================================================
# 生命周期管理
# =============================================================================


def start_video_ai_queue_processor() -> None:
    """
    启动视频 AI 队列处理器

    在应用启动时调用
    """
    global _queue_processor_task
    if _queue_processor_task is not None and not _queue_processor_task.done():
        return
    loop = asyncio.get_event_loop()
    _queue_processor_task = loop.create_task(_queue_processor_loop())
    logger.info("Video AI queue processor started")


async def stop_video_ai_queue_processor() -> None:
    """
    停止视频 AI 队列处理器

    在应用关闭时调用
    """
    global _queue_processor_task, _persist_worker_task

    # 取消所有正在运行的管道任务
    for tid, task in list(video_ai_worker_tasks.items()):
        if not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    # 取消队列处理器
    if _queue_processor_task and not _queue_processor_task.done():
        _queue_processor_task.cancel()
        try:
            await _queue_processor_task
        except asyncio.CancelledError:
            pass

    # 取消持久化任务
    if _persist_worker_task and not _persist_worker_task.done():
        _persist_worker_task.cancel()
        try:
            await _persist_worker_task
        except asyncio.CancelledError:
            pass

    logger.info("Video AI queue processor stopped")
