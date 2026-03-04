from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from uuid import UUID

import httpx

from app.core.config import settings
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


def _build_prompt(base_prompt: str, output_format: str, json_schema: str) -> str:
    """
    构建最终提示词：当 output_format 为 json 时，将 JSON schema 作为补充提示词追加。
    """
    if output_format != "json" or not json_schema.strip():
        return base_prompt
    schema_instruction = (
        "\n\n---\n"
        "请严格按照以下JSON格式返回结果，**不要包含任何其他内容**：\n"
        f"```json\n{json_schema.strip()}\n```\n"
        "重要：只返回JSON本身，不要有解释文字、注释、或多余的markdown标记。"
    )
    return base_prompt + schema_instruction


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


async def _call_image_gen_api(
    *,
    api_base_url: str,
    api_key: str,
    model_name: str,
    prompt: str,
    size: str = "1:1",
    quality: str = "2K",
    poll_interval: float = 3.0,
    poll_timeout: float = 300.0,
) -> str:
    """
    调用 EvoLink 图片生成 API（Job 轮询模式）。

    提交：POST /v1/images/generations
    轮询：GET  /v1/tasks/{task_id}

    Args:
        api_base_url: EvoLink API 基础 URL（如 https://api.evolink.ai）
        api_key:      EvoLink API 密钥
        model_name:   生图模型（如 gemini-3.1-flash-image-preview）
        prompt:       图片生成提示词
        size:         宽高比（auto/1:1/2:3/3:2/9:16/16:9 等）
        quality:      分辨率（0.5K/1K/2K/4K）
        poll_interval: 轮询间隔（秒）
        poll_timeout:  最大等待时间（秒）

    Returns:
        生成图片的 URL（来自 results 数组第一项）

    Raises:
        ValueError: 任务失败或 results 为空
        httpx.HTTPStatusError: HTTP 请求失败
        asyncio.TimeoutError: 超时
    """
    base = api_base_url.rstrip("/")
    submit_url = f"{base}/v1/images/generations"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    submit_payload: dict = {
        "model": model_name,
        "prompt": prompt,
        "size": size,
        "quality": quality,
    }

    masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
    logger.info("ImageGen submit: url=%s, model=%s, size=%s, quality=%s, api_key=%s",
                submit_url, model_name, size, quality, masked_key)
    logger.info("ImageGen prompt: %s", prompt[:200] if len(prompt) > 200 else prompt)

    async with httpx.AsyncClient(timeout=60.0) as client:
        # 步骤 1：提交生图任务
        submit_resp = await client.post(submit_url, json=submit_payload, headers=headers)
        if not submit_resp.is_success:
            logger.error("ImageGen submit error: status=%d, body=%s", submit_resp.status_code, submit_resp.text)
        submit_resp.raise_for_status()
        submit_data = submit_resp.json()
        logger.info("ImageGen submit response: %s", json.dumps(submit_data, ensure_ascii=False)[:500])

        # 提取 task_id（响应字段为 "id"）
        task_id = submit_data.get("id")
        if not task_id:
            raise ValueError(f"No task id in submit response: {submit_data}")
        logger.info("ImageGen task submitted: task_id=%s, status=%s", task_id, submit_data.get("status"))

        # 步骤 2：轮询任务状态
        poll_url = f"{base}/v1/tasks/{task_id}"
        elapsed = 0.0
        while elapsed < poll_timeout:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            poll_resp = await client.get(poll_url, headers=headers)
            if not poll_resp.is_success:
                logger.warning("ImageGen poll error: status=%d, task_id=%s, body=%s",
                               poll_resp.status_code, task_id, poll_resp.text[:200])
                poll_resp.raise_for_status()
            poll_data = poll_resp.json()
            status = (poll_data.get("status") or "").lower()
            progress = poll_data.get("progress", 0)
            logger.info("ImageGen poll: task_id=%s, status=%s, progress=%s, elapsed=%.0fs",
                        task_id, status, progress, elapsed)

            if status == "completed":
                # results 是字符串 URL 列表
                results = poll_data.get("results") or []
                if results and isinstance(results, list):
                    image_url = results[0]
                    logger.info("ImageGen completed: task_id=%s, url=%s", task_id, str(image_url)[:100])
                    return image_url
                raise ValueError(f"Task completed but results is empty: {poll_data}")

            if status == "failed":
                err_msg = poll_data.get("error") or poll_data.get("message") or str(poll_data)
                raise ValueError(f"ImageGen task failed (task_id={task_id}): {err_msg}")

            # pending / processing — 继续等待

        raise asyncio.TimeoutError(f"ImageGen task timed out after {poll_timeout}s (task_id={task_id})")


# =============================================================================
# 图片下载和上传
# =============================================================================


async def _download_and_upload_images(image_urls: list[str]) -> list[dict]:
    """
    从 URL 下载图片并上传到 CDN

    Args:
        image_urls: 图片 URL 列表

    Returns:
        上传后的图片信息列表: [{image_url, description}]
    """
    if not image_urls:
        return []

    upload_api_url = settings.video_image_upload_url
    results = []

    async with httpx.AsyncClient(timeout=60.0) as client:
        for idx, img_url in enumerate(image_urls):
            try:
                logger.info("Downloading image %d/%d: %s", idx + 1, len(image_urls), img_url)

                # 下载图片
                download_resp = await client.get(img_url)
                download_resp.raise_for_status()
                image_data = download_resp.content
                content_type = download_resp.headers.get("content-type", "image/png")

                # 上传到 CDN
                filename = f"outfit_{idx + 1}.png"
                files = {
                    "file": (filename, image_data, content_type)
                }

                upload_resp = await client.post(
                    upload_api_url,
                    files=files,
                    headers={"User-Agent": "confyUI-backend/1.0.0"}
                )
                upload_resp.raise_for_status()
                upload_result = upload_resp.json()

                if upload_result.get("code") != 0:
                    raise Exception(f"Upload failed: {upload_result.get('message', 'Unknown error')}")

                uploaded_url = upload_result.get("data", {}).get("url")
                if not uploaded_url:
                    raise Exception("No URL in upload response")

                logger.info("Successfully uploaded image %d to CDN: %s", idx + 1, uploaded_url)
                results.append({
                    "image_url": uploaded_url,
                    "description": f"穿搭图 {idx + 1}",
                })

            except Exception as exc:
                logger.error("Failed to process image %d (%s): %s", idx + 1, img_url, exc)
                # 保留原始 URL 作为备用
                results.append({
                    "image_url": img_url,
                    "description": f"穿搭图 {idx + 1}",
                    "error": str(exc),
                })

    return results


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

            # 加载 EvoLink 设置
            from app.services.evolink_settings_service import get_or_create_evolink_settings
            evo = await get_or_create_evolink_settings(session)
            api_key = evo.api_key
            api_base_url = evo.api_base_url
            # 步骤一：视频整体理解
            understand_model = evo.understand_model or evo.model_name or "gemini-3.1-pro-preview"
            understand_prompt = _build_prompt(
                evo.understand_prompt or "请描述这个视频的内容，包括场景、人物、服装风格等。",
                evo.understand_output_format,
                evo.understand_json_schema,
            )
            understand_temperature = evo.understand_temperature
            # 步骤二：造型描述提取
            extract_model = evo.extract_model or evo.model_name or "gemini-3.1-pro-preview"
            _default_extract_base = """请分析视频中出现的所有不同穿搭造型，以JSON数组格式返回每个造型的文字描述。"""
            extract_prompt = _build_prompt(
                evo.extract_prompt or _default_extract_base,
                evo.extract_output_format or "json",
                evo.extract_json_schema,
            )
            extract_temperature = evo.extract_temperature
            extract_output_format = evo.extract_output_format or "json"
            # 步骤三：生图（EvoLink Job 轮询模式）
            image_gen_model = evo.image_gen_model
            image_gen_prompt_template = evo.image_gen_prompt_template or "Generate a fashion outfit image: {description}"
            image_gen_size = evo.image_gen_size or "1:1"
            image_gen_quality = evo.image_gen_quality or "2K"

        try:
            # ========== 步骤 1: 视频整体理解 ==========
            _set_status(template_id, VideoAIProcessStatus.understanding)
            logger.info("[%s] understanding started", template_id)

            prompt_description = ""
            if video_url and api_key:
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

            # ========== 步骤 2: 提取造型描述 ==========
            _set_status(template_id, VideoAIProcessStatus.extracting)
            logger.info("[%s] extracting outfit descriptions started", template_id)

            outfit_descriptions: list[dict] = []

            if video_url and api_key:
                raw = await _call_evolink_api(
                    api_base_url=api_base_url,
                    api_key=api_key,
                    model_name=extract_model,
                    video_url=video_url,
                    prompt=extract_prompt,
                    temperature=extract_temperature,
                )

                logger.info("[%s] Raw extract response: %s", template_id, raw[:1000] if len(raw) > 1000 else raw)

                if extract_output_format == "json":
                    # 解析 JSON 格式的造型列表
                    try:
                        clean = raw.strip()
                        if clean.startswith("```"):
                            lines = clean.split("\n")
                            clean = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
                        parsed = json.loads(clean)
                        if isinstance(parsed, list):
                            outfit_descriptions = [
                                {"id": i + 1, "description": item.get("description", str(item))}
                                if isinstance(item, dict) else {"id": i + 1, "description": str(item)}
                                for i, item in enumerate(parsed)
                            ]
                        elif isinstance(parsed, dict):
                            outfits = parsed.get("outfits") or parsed.get("items") or [parsed]
                            outfit_descriptions = [
                                {"id": i + 1, "description": item.get("description", str(item))}
                                if isinstance(item, dict) else {"id": i + 1, "description": str(item)}
                                for i, item in enumerate(outfits)
                            ]
                        else:
                            outfit_descriptions = [{"id": 1, "description": str(parsed)}]
                    except Exception as exc:
                        logger.info("[%s] JSON parse failed, treating as markdown: %s", template_id, exc)
                        # 按段落分割作为各造型描述
                        paragraphs = [p.strip() for p in raw.split("\n\n") if p.strip()]
                        outfit_descriptions = [{"id": i + 1, "description": p} for i, p in enumerate(paragraphs)]
                else:
                    # markdown 格式：按段落或列表项分割
                    lines = [l.strip().lstrip("- *•0123456789.").strip() for l in raw.split("\n") if l.strip() and len(l.strip()) > 10]
                    outfit_descriptions = [{"id": i + 1, "description": l} for i, l in enumerate(lines)]

                logger.info("[%s] Extracted %d outfit descriptions", template_id, len(outfit_descriptions))

            # 存储提取的造型描述（不含图片，等待步骤3生成）
            initial_shots = [{"id": d["id"], "description": d["description"], "image_url": None} for d in outfit_descriptions]
            state = video_ai_states.setdefault(template_id, _new_state(template_id, VideoAIProcessStatus.extracting))
            state["extracted_shots"] = initial_shots
            state["updated_at"] = _utcnow_iso()
            _mark_dirty(template_id)

            # ========== 步骤 3: 并发调用生图模型 ==========
            if outfit_descriptions and image_gen_model:
                _set_status(template_id, VideoAIProcessStatus.downloading)
                logger.info("[%s] generating images for %d outfits (model=%s)", template_id, len(outfit_descriptions), image_gen_model)

                async def _gen_image(outfit: dict) -> dict:
                    desc = outfit["description"]
                    prompt_text = image_gen_prompt_template.replace("{description}", desc)
                    try:
                        evolink_url = await _call_image_gen_api(
                            api_base_url=api_base_url,
                            api_key=api_key,
                            model_name=image_gen_model,
                            prompt=prompt_text,
                            size=image_gen_size,
                            quality=image_gen_quality,
                        )
                        logger.info("[%s] Generated image for outfit %s: %s", template_id, outfit["id"], evolink_url[:100] if evolink_url else "")
                        # 下载并上传到 CDN
                        uploaded = await _download_and_upload_images([evolink_url])
                        cdn_url = uploaded[0]["image_url"] if uploaded else evolink_url
                        logger.info("[%s] CDN url for outfit %s: %s", template_id, outfit["id"], cdn_url[:100] if cdn_url else "")
                        return {"id": outfit["id"], "description": desc, "image_url": cdn_url}
                    except Exception as exc:
                        logger.error("[%s] Failed to generate image for outfit %s: %s", template_id, outfit["id"], exc)
                        return {"id": outfit["id"], "description": desc, "image_url": None, "error": str(exc)}

                # 并发调用，最多3个同时
                gen_semaphore = asyncio.Semaphore(3)

                async def _gen_with_sem(outfit: dict) -> dict:
                    async with gen_semaphore:
                        return await _gen_image(outfit)

                generated_shots = await asyncio.gather(*[_gen_with_sem(o) for o in outfit_descriptions])

                state = video_ai_states.setdefault(template_id, _new_state(template_id, VideoAIProcessStatus.downloading))
                state["extracted_shots"] = list(generated_shots)
                state["updated_at"] = _utcnow_iso()
                _mark_dirty(template_id)

                # 立即持久化生成的图片到数据库
                async with SessionLocal() as session:
                    tpl = await session.get(VideoAITemplate, uuid_val)
                    if tpl:
                        tpl.extracted_shots = list(generated_shots)
                        await session.commit()

            elif outfit_descriptions:
                # 无生图模型配置，仅存描述
                logger.info("[%s] No image gen model configured, storing descriptions only", template_id)
                async with SessionLocal() as session:
                    tpl = await session.get(VideoAITemplate, uuid_val)
                    if tpl:
                        tpl.extracted_shots = initial_shots
                        await session.commit()

            # ========== 步骤 4: 成功 ==========
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
    try:
        while True:
            template_id = await video_ai_queue.get()
            task = asyncio.get_running_loop().create_task(_run_pipeline(template_id, semaphore))
            video_ai_worker_tasks[template_id] = task
            video_ai_queue.task_done()
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Video AI queue processor crashed")


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
