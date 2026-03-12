from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

import httpx

from app.db.session import SessionLocal

logger = logging.getLogger("app.ai_account")

# =============================================================================
# 全局变量
# =============================================================================

ai_account_states: dict[str, dict] = {}
dirty_ai_account_ids: set[str] = set()
ai_account_worker_tasks: dict[str, asyncio.Task] = {}
ai_account_queue: asyncio.Queue[str] = asyncio.Queue()

_queue_processor_task: asyncio.Task | None = None
_persist_worker_task: asyncio.Task | None = None

_CONCURRENCY = 3
_PERSIST_INTERVAL = 2.0
_IMAGEGEN_POLL_INTERVAL = 5.0
_IMAGEGEN_POLL_TIMEOUT = 300.0


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _upload_remote_image_to_cdn(image_url: str, filename: str) -> str:
    """Download upstream image and re-upload to our CDN, returning the CDN URL."""
    from app.services.upload_service import UpstreamImageUploadService

    async with httpx.AsyncClient(timeout=120.0, trust_env=False) as client:
        dl = await client.get(image_url)
        dl.raise_for_status()

    content_type = dl.headers.get("content-type", "image/png").split(";", 1)[0].strip() or "image/png"
    svc = UpstreamImageUploadService()
    upload_result = await svc.upload_image(dl.content, content_type, filename)
    return upload_result.url


# =============================================================================
# 状态管理
# =============================================================================


def _new_state(account_id: str, status: str) -> dict:
    return {
        "account_id": account_id,
        "status": status,
        "error_message": "",
        "selected_tag_ids": [],
        "video_descriptions": [],
        "combined_description": "",
        "generated_name": "",
        "generated_avatar_url": "",
        "generated_photo_url": "",
        "completed_stages": [],
        "updated_at": _utcnow_iso(),
    }


def _mark_dirty(account_id: str) -> None:
    dirty_ai_account_ids.add(account_id)


def _set_status(account_id: str, status: str, *, error: str = "") -> None:
    state = ai_account_states.setdefault(account_id, _new_state(account_id, status))
    state["status"] = status
    state["error_message"] = error
    state["updated_at"] = _utcnow_iso()
    _mark_dirty(account_id)


def get_ai_account_state(account_id: str) -> dict | None:
    return ai_account_states.get(account_id)


# =============================================================================
# 数据库持久化
# =============================================================================


async def _persist_states(account_ids: list[str]) -> None:
    if not account_ids:
        return
    from app.models.account import Account
    async with SessionLocal() as session:
        for aid in account_ids:
            state = ai_account_states.get(aid)
            if state is None:
                continue
            try:
                uuid_val = UUID(aid)
            except ValueError:
                continue
            acc = await session.get(Account, uuid_val)
            if not acc:
                continue
            acc.ai_generation_status = state["status"]
            acc.ai_generation_error = state.get("error_message") or None
            acc.ai_generation_state = state
            if state.get("generated_name"):
                acc.account_name = state["generated_name"]
            if state.get("generated_avatar_url"):
                acc.avatar_url = state["generated_avatar_url"]
            if state.get("generated_photo_url"):
                acc.photo_url = state["generated_photo_url"]
        await session.commit()


async def _persist_worker_loop() -> None:
    global _persist_worker_task
    try:
        while True:
            await asyncio.sleep(_PERSIST_INTERVAL)
            ids = list(dirty_ai_account_ids)
            if not ids:
                continue
            dirty_ai_account_ids.difference_update(ids)
            await _persist_states(ids)
    except asyncio.CancelledError:
        ids = list(dirty_ai_account_ids)
        if ids:
            dirty_ai_account_ids.difference_update(ids)
            await _persist_states(ids)
        raise
    except Exception:
        logger.exception("AI account persist worker crashed")


def _ensure_persist_worker() -> None:
    global _persist_worker_task
    if _persist_worker_task is not None and not _persist_worker_task.done():
        return
    loop = asyncio.get_running_loop()
    _persist_worker_task = loop.create_task(_persist_worker_loop())


# =============================================================================
# EvoLink API 调用（纯文本，无视频）
# =============================================================================


async def _call_evolink_text(
    *,
    api_base_url: str,
    api_key: str,
    model_name: str,
    prompt: str,
    temperature: float = 0.7,
) -> str:
    """调用 EvoLink (Gemini 协议) 进行纯文本生成。"""
    url = f"{api_base_url.rstrip('/')}/v1beta/models/{model_name}:generateContent"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature},
    }
    masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
    logger.info("EvoLink text API: model=%s, api_key=%s, prompt_len=%d", model_name, masked_key, len(prompt))

    async with httpx.AsyncClient(timeout=120.0, trust_env=False) as client:
        resp = await client.post(url, json=payload, headers={"Authorization": f"Bearer {api_key}"})
        if not resp.is_success:
            logger.error("EvoLink text API error: status=%d, body=%s", resp.status_code, resp.text[:1000])
            raise ValueError(f"EvoLink text API HTTP {resp.status_code}: {resp.text[:500]}")
        data = resp.json()

    logger.debug("EvoLink text API raw response: %s", json.dumps(data, ensure_ascii=False)[:500])
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return text.strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"Unexpected EvoLink response format: {data}") from exc


async def _call_evolink_video(
    *,
    api_base_url: str,
    api_key: str,
    model_name: str,
    video_url: str,
    prompt: str,
    temperature: float = 0.3,
) -> str:
    """调用 EvoLink (Gemini 协议) 进行视频分析，返回文字描述。"""
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
    logger.info("EvoLink video API: model=%s, video_url=%s", model_name, video_url)

    async with httpx.AsyncClient(timeout=120.0, trust_env=False) as client:
        resp = await client.post(url, json=payload, headers={"Authorization": f"Bearer {api_key}"})
        if not resp.is_success:
            logger.error("EvoLink video API error: status=%d, body=%s", resp.status_code, resp.text[:1000])
            raise ValueError(f"EvoLink video API HTTP {resp.status_code}: {resp.text[:500]}")
        data = resp.json()

    logger.debug("EvoLink video API response: %s", str(data)[:500])
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return text.strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"Unexpected EvoLink response format: {data}") from exc


# =============================================================================
# Nano2 头像生成
# =============================================================================


async def _submit_nano2_avatar_job(
    *,
    api_base_url: str,
    api_key: str,
    prompt: str,
    model: str,
    size: str,
    quality: str,
    image_urls: list[str] | None = None,
) -> str:
    """提交 Nano2 生图任务，支持纯文本或附带参考图，返回 task_id。"""
    url = f"{api_base_url.rstrip('/')}/v1/images/generations"
    payload = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "quality": quality,
    }
    if image_urls:
        payload["image_urls"] = image_urls
    async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
        resp = await client.post(url, json=payload, headers={"Authorization": f"Bearer {api_key}"})
        if not resp.is_success:
            logger.error("Nano2 avatar submit error: status=%d, body=%s", resp.status_code, resp.text)
        resp.raise_for_status()
        data = resp.json()
    task_id = data.get("id")
    if not task_id:
        raise ValueError(f"Nano2 avatar response missing task id: {data}")
    logger.info("Nano2 avatar task submitted: task_id=%s", task_id)
    return task_id


async def _poll_nano2_task(
    *,
    api_base_url: str,
    api_key: str,
    task_id: str,
) -> str:
    """轮询 Nano2 任务直到完成，返回结果图片 URL。"""
    url = f"{api_base_url.rstrip('/')}/v1/tasks/{task_id}"
    deadline = asyncio.get_event_loop().time() + _IMAGEGEN_POLL_TIMEOUT
    while True:
        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {api_key}"})
            resp.raise_for_status()
            data = resp.json()
        task_status = data.get("status")
        logger.debug("Nano2 avatar task %s: status=%s", task_id, task_status)
        if task_status == "completed":
            results = data.get("results", [])
            if not results:
                raise ValueError(f"Nano2 task {task_id} completed but no results")
            return results[0]
        if task_status == "failed":
            raise ValueError(f"Nano2 task {task_id} failed")
        if asyncio.get_event_loop().time() >= deadline:
            raise TimeoutError(f"Nano2 task {task_id} timed out after {_IMAGEGEN_POLL_TIMEOUT}s")
        await asyncio.sleep(_IMAGEGEN_POLL_INTERVAL)


# =============================================================================
# 照片生成（两步：视频描述 → Nano2 生图）
# =============================================================================


async def _generate_photo(
    *,
    account_id: str,
    video_urls: list[str],
    photo_video_prompt: str,
    photo_image_prompt: str,
    api_base_url: str,
    api_key: str,
    understand_model: str,
    avatar_model: str,
    avatar_size: str,
    avatar_quality: str,
) -> str:
    """
    博主照片生成：
    步骤1：随机选一个视频URL，用 photo_video_prompt 调用 Gemini 获取文字描述
    步骤2：用 photo_image_prompt + 描述 调用 Nano2 生成照片
    """
    import random
    if not video_urls:
        logger.warning("[%s] No video URLs for photo generation", account_id)
        return ""

    video_url = random.choice(video_urls)
    logger.info("[%s] photo generation: analyzing video %s...", account_id, video_url[:80])

    # 步骤1：视频理解 → 文字描述（最多重试3次）
    desc_prompt = photo_video_prompt or "请详细描述视频中人物的外貌特征、肤色、发型、表情、体型等，用于生成写实人物照片。"
    last_exc: Exception | None = None
    description = ""
    for attempt in range(1, 4):
        try:
            description = await _call_evolink_video(
                api_base_url=api_base_url,
                api_key=api_key,
                model_name=understand_model,
                video_url=video_url,
                prompt=desc_prompt,
            )
            last_exc = None
            break
        except Exception as exc:
            last_exc = exc
            logger.warning("[%s] photo video analysis attempt %d/3 failed: %s", account_id, attempt, exc)
    if last_exc is not None:
        raise last_exc  # type: ignore[misc]
    logger.info("[%s] photo generation: got description (len=%d), submitting to Nano2...", account_id, len(description))

    # 步骤2：Nano2 生图（最多重试3次）
    image_prompt = f"{photo_image_prompt}\n\n人物描述：{description}" if photo_image_prompt else description
    result_url = ""
    for attempt in range(1, 4):
        try:
            task_id = await _submit_nano2_avatar_job(
                api_base_url=api_base_url,
                api_key=api_key,
                prompt=image_prompt,
                model=avatar_model,
                size=avatar_size,
                quality=avatar_quality,
            )
            result_url = await _poll_nano2_task(api_base_url=api_base_url, api_key=api_key, task_id=task_id)
            last_exc = None
            break
        except Exception as exc:
            last_exc = exc
            logger.warning("[%s] photo Nano2 attempt %d/3 failed: %s", account_id, attempt, exc)
    if last_exc is not None:
        raise last_exc  # type: ignore[misc]

    cdn_url = await _upload_remote_image_to_cdn(result_url, "photo.png")
    logger.info("[%s] Photo uploaded to CDN: %s", account_id, cdn_url[:80])
    return cdn_url


# =============================================================================
# 各阶段处理函数
# =============================================================================


async def _stage_video_analysis(
    account_id: str,
    video_urls: list[str],
    api_base_url: str,
    api_key: str,
    model_name: str,
    prompt: str,
) -> str:
    """
    阶段1: 并发分析视频，将每个视频的描述拼接为完整描述字符串。
    每段描述用 ``` 包裹。
    """
    state = ai_account_states.get(account_id, {})
    if "video_analyzing" in state.get("completed_stages", []):
        logger.info("[%s] video_analyzing skipped (already completed)", account_id)
        return state.get("combined_description", "")

    _set_status(account_id, "video_analyzing")
    logger.info("[%s] video_analyzing started, %d videos", account_id, len(video_urls))

    async def _analyze_one(url: str) -> str:
        last_exc: Exception | None = None
        for attempt in range(1, 4):
            try:
                return await _call_evolink_video(
                    api_base_url=api_base_url,
                    api_key=api_key,
                    model_name=model_name,
                    video_url=url,
                    prompt=prompt,
                )
            except Exception as exc:
                last_exc = exc
                logger.warning("[%s] video analysis attempt %d/3 failed for %s: %s", account_id, attempt, url[:60], exc)
        raise last_exc  # type: ignore[misc]

    tasks = [_analyze_one(url) for url in video_urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    valid_descriptions = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            logger.warning("[%s] video[%d] analysis failed: %s", account_id, i, r)
        else:
            valid_descriptions.append(f"```\n{r}\n```")

    if not valid_descriptions:
        raise ValueError("所有视频分析均失败，无法生成描述")

    combined = "\n\n".join(valid_descriptions)
    state = ai_account_states[account_id]
    state["video_descriptions"] = valid_descriptions
    state["combined_description"] = combined
    if "video_analyzing" not in state.get("completed_stages", []):
        state.setdefault("completed_stages", []).append("video_analyzing")
    _mark_dirty(account_id)
    await _persist_states([account_id])
    logger.info("[%s] video_analyzing done: %d/%d succeeded, combined_len=%d",
                account_id, len(valid_descriptions), len(video_urls), len(combined))
    return combined


async def _stage_name_generation(
    account_id: str,
    combined_description: str,
    api_base_url: str,
    api_key: str,
    model_name: str,
    name_prompt: str,
) -> str:
    """阶段2: 基于视频描述，调用 Gemini 生成博主名称。"""
    state = ai_account_states.get(account_id, {})
    if "name_generating" in state.get("completed_stages", []):
        logger.info("[%s] name_generating skipped (already completed)", account_id)
        return state.get("generated_name", "")

    _set_status(account_id, "name_generating")
    logger.info("[%s] name_generating started", account_id)

    full_prompt = f"{name_prompt}\n\n参考视频内容描述：\n{combined_description}" if name_prompt else f"根据以下视频内容描述，为这个博主取一个有吸引力的名字，直接输出名字即可：\n{combined_description}"

    last_exc: Exception | None = None
    name = ""
    for attempt in range(1, 4):
        try:
            name = await _call_evolink_text(
                api_base_url=api_base_url,
                api_key=api_key,
                model_name=model_name,
                prompt=full_prompt,
                temperature=0.9,
            )
            last_exc = None
            break
        except Exception as exc:
            last_exc = exc
            logger.warning("[%s] name_generating attempt %d/3 failed: %s", account_id, attempt, exc)
    if last_exc is not None:
        raise last_exc  # type: ignore[misc]

    state = ai_account_states[account_id]
    state["generated_name"] = name
    if "name_generating" not in state.get("completed_stages", []):
        state.setdefault("completed_stages", []).append("name_generating")
    _mark_dirty(account_id)
    await _persist_states([account_id])
    logger.info("[%s] name_generating done: name=%s", account_id, name[:50])
    return name


async def _stage_avatar_generation(
    account_id: str,
    combined_description: str,
    reference_photo_url: str,
    api_base_url: str,
    api_key: str,
    avatar_model: str,
    avatar_prompt: str,
    avatar_size: str,
    avatar_quality: str,
) -> str:
    """基于参考照片和视频描述，调用 Nano2 生成博主头像，上传到 CDN，返回头像 URL。"""
    state = ai_account_states.get(account_id, {})
    if "avatar_generating" in state.get("completed_stages", []):
        logger.info("[%s] avatar_generating skipped (already completed)", account_id)
        return state.get("generated_avatar_url", "")

    _set_status(account_id, "avatar_generating")
    logger.info("[%s] avatar_generating started", account_id)

    prompt_parts: list[str] = []
    if avatar_prompt:
        prompt_parts.append(avatar_prompt)
    else:
        prompt_parts.append("请基于参考照片和以下视频内容描述生成一张博主头像。")
    prompt_parts.append(f"参考视频内容描述：\n{combined_description}")
    full_prompt = "\n\n".join(prompt_parts)

    last_exc: Exception | None = None
    result_url = ""
    for attempt in range(1, 4):
        try:
            task_id = await _submit_nano2_avatar_job(
                api_base_url=api_base_url,
                api_key=api_key,
                prompt=full_prompt,
                model=avatar_model,
                size=avatar_size,
                quality=avatar_quality,
                image_urls=[reference_photo_url] if reference_photo_url else None,
            )
            logger.info("[%s] Nano2 avatar task submitted: %s, polling… (attempt %d/3)", account_id, task_id, attempt)
            result_url = await _poll_nano2_task(api_base_url=api_base_url, api_key=api_key, task_id=task_id)
            last_exc = None
            break
        except Exception as exc:
            last_exc = exc
            logger.warning("[%s] avatar_generating attempt %d/3 failed: %s", account_id, attempt, exc)
    if last_exc is not None:
        raise last_exc  # type: ignore[misc]

    cdn_url = await _upload_remote_image_to_cdn(result_url, "avatar.png")
    logger.info("[%s] Avatar uploaded to CDN: %s", account_id, cdn_url[:80])

    state = ai_account_states[account_id]
    state["generated_avatar_url"] = cdn_url
    if "avatar_generating" not in state.get("completed_stages", []):
        state.setdefault("completed_stages", []).append("avatar_generating")
    _mark_dirty(account_id)
    await _persist_states([account_id])
    logger.info("[%s] avatar_generating done: url=%s", account_id, cdn_url[:80])
    return cdn_url


async def _stage_photo_generation(
    account_id: str,
    video_urls: list[str],
    photo_video_prompt: str,
    photo_image_prompt: str,
    api_base_url: str,
    api_key: str,
    understand_model: str,
    avatar_model: str,
    avatar_size: str,
    avatar_quality: str,
) -> str:
    """阶段4: 生成博主照片（视频描述 → Nano2 生图）。"""
    state = ai_account_states.get(account_id, {})
    if "photo_generating" in state.get("completed_stages", []):
        logger.info("[%s] photo_generating skipped (already completed)", account_id)
        return state.get("generated_photo_url", "")

    _set_status(account_id, "photo_generating")

    photo_url = await _generate_photo(
        account_id=account_id,
        video_urls=video_urls,
        photo_video_prompt=photo_video_prompt,
        photo_image_prompt=photo_image_prompt,
        api_base_url=api_base_url,
        api_key=api_key,
        understand_model=understand_model,
        avatar_model=avatar_model,
        avatar_size=avatar_size,
        avatar_quality=avatar_quality,
    )

    state = ai_account_states[account_id]
    state["generated_photo_url"] = photo_url
    if "photo_generating" not in state.get("completed_stages", []):
        state.setdefault("completed_stages", []).append("photo_generating")
    _mark_dirty(account_id)
    await _persist_states([account_id])
    return photo_url


# =============================================================================
# 主管道
# =============================================================================


async def _run_pipeline(account_id: str, semaphore: asyncio.Semaphore) -> None:
    async with semaphore:
        try:
            # 从数据库加载账号、配置和关联的视频
            from app.models.account import Account
            from app.models.account_tag import AccountTag
            from app.models.video_source import VideoSource
            from app.models.tag import VideoSourceTag
            from app.services.system_settings_service import get_or_create_system_settings
            from app.services.pipeline_settings_service import get_or_create_pipeline_settings
            from sqlalchemy import select

            async with SessionLocal() as session:
                try:
                    uuid_val = UUID(account_id)
                except ValueError:
                    return
                acc = await session.get(Account, uuid_val)
                if not acc:
                    logger.warning("[%s] Account not found", account_id)
                    return

                sys_cfg = await get_or_create_system_settings(session)
                api_key = sys_cfg.evolink_api_key
                api_base_url = sys_cfg.evolink_api_base_url

                if not api_key:
                    raise ValueError("系统未配置 EvoLink API Key，请前往【系统设置】进行配置。")

                # 加载流程配置
                if acc.owner_id is not None:
                    pipeline_cfg = await get_or_create_pipeline_settings(session, owner_id=acc.owner_id)
                    video_prompt = pipeline_cfg.ai_account_video_prompt or "请用中文详细描述这个视频的内容，包括场景、人物特征、服装风格、行为动作等。"
                    video_model = pipeline_cfg.ai_account_video_model or "gemini-3.1-pro-preview"
                    name_prompt = pipeline_cfg.ai_account_name_prompt or ""
                    avatar_prompt = pipeline_cfg.ai_account_avatar_prompt or ""
                    photo_video_prompt = pipeline_cfg.ai_account_photo_video_prompt or ""
                    photo_image_prompt = pipeline_cfg.ai_account_photo_image_prompt or ""
                    name_model = pipeline_cfg.ai_account_name_model or "gemini-2.5-flash"
                    avatar_model = pipeline_cfg.ai_account_avatar_model or "gemini-3.1-flash-image-preview"
                    avatar_size = pipeline_cfg.ai_account_avatar_size or "1:1"
                    avatar_quality = pipeline_cfg.ai_account_avatar_quality or "1K"
                else:
                    video_prompt = "请用中文详细描述这个视频的内容，包括场景、人物特征、服装风格、行为动作等。"
                    video_model = "gemini-3.1-pro-preview"
                    name_prompt = ""
                    avatar_prompt = ""
                    photo_video_prompt = ""
                    photo_image_prompt = ""
                    name_model = "gemini-2.5-flash"
                    avatar_model = "gemini-3.1-flash-image-preview"
                    avatar_size = "1:1"
                    avatar_quality = "1K"

                # 标签来源以数据库为准。触发生成前会先把标签绑定到账号，
                # 因此这里直接查询账号当前绑定的标签，不依赖内存状态。
                bound_tag_ids = (
                    await session.execute(
                        select(AccountTag.tag_id).where(AccountTag.account_id == acc.id)
                    )
                ).scalars().all()
                tag_ids = [str(tag_id) for tag_id in bound_tag_ids]
                state = ai_account_states.setdefault(account_id, _new_state(account_id, "pending"))
                state["selected_tag_ids"] = tag_ids
                _mark_dirty(account_id)

                # 根据标签查询关联的视频（最多10个，优先使用已下载的本地URL）
                video_urls: list[str] = []
                if tag_ids:
                    tag_uuid_list = [UUID(tid) for tid in tag_ids if isinstance(tid, str)]
                    stmt = (
                        select(VideoSource)
                        .join(VideoSourceTag, VideoSourceTag.video_source_id == VideoSource.id)
                        .where(VideoSourceTag.tag_id.in_(tag_uuid_list))
                        .order_by(VideoSource.created_at.desc())
                        .limit(10)
                    )
                    rows = (await session.execute(stmt)).scalars().all()
                    for vs in rows:
                        url = vs.local_video_url or vs.video_url
                        if url:
                            video_urls.append(url)

            if not video_urls:
                raise ValueError("选中的标签没有关联的视频，无法生成博主内容")

            logger.info("[%s] pipeline started: %d videos, tag_ids=%s", account_id, len(video_urls), tag_ids)

            # 阶段1：视频分析
            combined_description = await _stage_video_analysis(
                account_id=account_id,
                video_urls=video_urls,
                api_base_url=api_base_url,
                api_key=api_key,
                model_name=video_model,
                prompt=video_prompt,
            )

            # 阶段2：生成博主名称
            await _stage_name_generation(
                account_id=account_id,
                combined_description=combined_description,
                api_base_url=api_base_url,
                api_key=api_key,
                model_name=name_model,
                name_prompt=name_prompt,
            )

            # 阶段3：先生成博主照片
            generated_photo_url = await _stage_photo_generation(
                account_id=account_id,
                video_urls=video_urls,
                photo_video_prompt=photo_video_prompt,
                photo_image_prompt=photo_image_prompt,
                api_base_url=api_base_url,
                api_key=api_key,
                understand_model=video_model,
                avatar_model=avatar_model,
                avatar_size=avatar_size,
                avatar_quality=avatar_quality,
            )

            # 阶段4：基于照片 + 配置提示词 + 视频描述生成博主头像
            await _stage_avatar_generation(
                account_id=account_id,
                combined_description=combined_description,
                reference_photo_url=generated_photo_url,
                api_base_url=api_base_url,
                api_key=api_key,
                avatar_model=avatar_model,
                avatar_prompt=avatar_prompt,
                avatar_size=avatar_size,
                avatar_quality=avatar_quality,
            )

            _set_status(account_id, "completed")
            logger.info("[%s] pipeline completed", account_id)
            await _persist_states([account_id])

        except asyncio.CancelledError:
            _set_status(account_id, "failed", error="任务被取消")
            await _persist_states([account_id])
            raise
        except Exception as exc:
            logger.exception("[%s] pipeline failed: %s", account_id, exc)
            _set_status(account_id, "failed", error=str(exc))
            await _persist_states([account_id])
        finally:
            ai_account_worker_tasks.pop(account_id, None)


# =============================================================================
# 队列处理器
# =============================================================================


async def _queue_processor_loop() -> None:
    semaphore = asyncio.Semaphore(_CONCURRENCY)
    while True:
        try:
            account_id = await ai_account_queue.get()
            task = asyncio.get_running_loop().create_task(_run_pipeline(account_id, semaphore))
            ai_account_worker_tasks[account_id] = task
            ai_account_queue.task_done()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("AI account queue processor error, continuing")


# =============================================================================
# 公共 API
# =============================================================================


async def enqueue_ai_account_generation(account_id: str, tag_ids: list[str]) -> None:
    """将账号加入 AI 生成队列。tag_ids 为需要分析的标签 ID 列表。"""
    state = ai_account_states.setdefault(account_id, _new_state(account_id, "pending"))
    state["status"] = "pending"
    state["error_message"] = ""
    state["selected_tag_ids"] = tag_ids
    # 清空已完成阶段，从头重跑
    state["completed_stages"] = []
    state["video_descriptions"] = []
    state["combined_description"] = ""
    state["generated_name"] = ""
    state["generated_avatar_url"] = ""
    state["generated_photo_url"] = ""
    state["updated_at"] = _utcnow_iso()
    _mark_dirty(account_id)

    _ensure_persist_worker()
    await _persist_states([account_id])
    dirty_ai_account_ids.discard(account_id)
    await ai_account_queue.put(account_id)
    logger.info("[%s] AI account generation enqueued, tag_ids=%s", account_id, tag_ids)


async def resume_ai_account_generation(account_id: str) -> None:
    """断点续跑：从上次失败/暂停处继续，保留已完成阶段。"""
    # 从数据库恢复状态（如果内存中没有）
    if account_id not in ai_account_states:
        try:
            uuid_val = UUID(account_id)
            from app.models.account import Account
            async with SessionLocal() as session:
                acc = await session.get(Account, uuid_val)
                if acc and acc.ai_generation_state:
                    ai_account_states[account_id] = acc.ai_generation_state
                    logger.info("[%s] restored state from DB: completed_stages=%s",
                                account_id, acc.ai_generation_state.get("completed_stages", []))
        except Exception as exc:
            logger.warning("[%s] failed to restore state from DB: %s", account_id, exc)

    state = ai_account_states.setdefault(account_id, _new_state(account_id, "pending"))
    state["status"] = "pending"
    state["error_message"] = ""
    state["updated_at"] = _utcnow_iso()
    # 保留 completed_stages、combined_description、generated_name 等已完成的数据
    _mark_dirty(account_id)

    _ensure_persist_worker()
    await _persist_states([account_id])
    dirty_ai_account_ids.discard(account_id)
    await ai_account_queue.put(account_id)
    logger.info("[%s] AI account generation resumed, completed_stages=%s",
                account_id, state.get("completed_stages", []))


async def restart_ai_account_generation(account_id: str, tag_ids: list[str] | None = None) -> None:
    """从头重试：清空所有已完成阶段，重新执行完整流程。"""
    # 先从 DB 取现有 tag_ids（如果未传入）
    if tag_ids is None:
        existing_state = ai_account_states.get(account_id)
        if existing_state:
            tag_ids = existing_state.get("selected_tag_ids", [])
        else:
            try:
                uuid_val = UUID(account_id)
                from app.models.account import Account
                async with SessionLocal() as session:
                    acc = await session.get(Account, uuid_val)
                    if acc and acc.ai_generation_state:
                        tag_ids = acc.ai_generation_state.get("selected_tag_ids", [])
            except Exception:
                pass
        tag_ids = tag_ids or []

    state = ai_account_states.setdefault(account_id, _new_state(account_id, "pending"))
    state["status"] = "pending"
    state["error_message"] = ""
    state["selected_tag_ids"] = tag_ids
    state["completed_stages"] = []
    state["video_descriptions"] = []
    state["combined_description"] = ""
    state["generated_name"] = ""
    state["generated_avatar_url"] = ""
    state["generated_photo_url"] = ""
    state["updated_at"] = _utcnow_iso()
    _mark_dirty(account_id)

    _ensure_persist_worker()
    await _persist_states([account_id])
    dirty_ai_account_ids.discard(account_id)
    await ai_account_queue.put(account_id)
    logger.info("[%s] AI account generation restarted from scratch, tag_ids=%s", account_id, tag_ids)


def start_ai_account_queue_processor() -> None:
    global _queue_processor_task
    if _queue_processor_task is not None and not _queue_processor_task.done():
        return
    loop = asyncio.get_running_loop()
    _queue_processor_task = loop.create_task(_queue_processor_loop())
    logger.info("AI account queue processor started")


async def stop_ai_account_queue_processor() -> None:
    global _queue_processor_task, _persist_worker_task
    if _queue_processor_task and not _queue_processor_task.done():
        _queue_processor_task.cancel()
        try:
            await _queue_processor_task
        except asyncio.CancelledError:
            pass
    if _persist_worker_task and not _persist_worker_task.done():
        _persist_worker_task.cancel()
        try:
            await _persist_worker_task
        except asyncio.CancelledError:
            pass
    logger.info("AI account queue processor stopped")


async def recover_stuck_accounts_on_startup() -> None:
    """启动时恢复所有卡在生成状态的账号任务。"""
    from app.models.account import Account
    from sqlalchemy import select

    async with SessionLocal() as session:
        # 查找所有状态不是 idle/completed/failed 的账号
        stuck_statuses = ["pending", "video_analyzing", "name_generating", "avatar_generating", "photo_generating"]
        stmt = (
            select(Account)
            .where(Account.ai_generation_status.in_(stuck_statuses))
            .where(Account.ai_generation_error.is_(None))  # 只处理没有错误的
        )
        accounts = (await session.execute(stmt)).scalars().all()

        for acc in accounts:
            account_id = str(acc.id)
            state = acc.ai_generation_state
            if state is None:
                # 没有状态，创建初始状态
                state = _new_state(account_id, "pending")
                # 尝试从 ai_generation_state 恢复 tag_ids
                try:
                    saved_state = json.loads(acc.ai_generation_state) if acc.ai_generation_state else {}
                    state["selected_tag_ids"] = saved_state.get("selected_tag_ids", [])
                except:
                    state["selected_tag_ids"] = []
            else:
                state = state
                # 恢复状态
                state["status"] = acc.ai_generation_status

            # 将账号状态恢复到内存
            ai_account_states[account_id] = state
            _mark_dirty(account_id)

            # 重新加入队列
            await ai_account_queue.put(account_id)
            logger.info("[%s] Recovered stuck account on startup: status=%s", account_id, acc.ai_generation_status)

    if accounts:
        await _persist_states([str(acc.id) for acc in accounts])
