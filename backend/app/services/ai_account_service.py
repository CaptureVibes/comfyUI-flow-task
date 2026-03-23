from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import httpx

from app.db.session import SessionLocal

logger = logging.getLogger("app.ai_account")

# =============================================================================
# 全局变量
# =============================================================================

ai_account_states: dict[str, dict[str, Any]] = {}
dirty_ai_account_ids: set[str] = set()
ai_account_worker_tasks: dict[str, asyncio.Task] = {}
ai_account_queue: asyncio.Queue[str] = asyncio.Queue()

_queue_processor_task: asyncio.Task | None = None
_persist_worker_task: asyncio.Task | None = None

_CONCURRENCY = 3
_PERSIST_INTERVAL = 2.0
_IMAGEGEN_POLL_INTERVAL = 5.0
_IMAGEGEN_POLL_TIMEOUT = 300.0
_IMAGE_PROMPT_MAX_CHARS = 2200
_PHOTO_SOURCE_VIDEO_COUNT = 3
_PHOTO_CANDIDATES_PER_VIDEO = 3
_PHOTO_CANDIDATE_COUNT = _PHOTO_SOURCE_VIDEO_COUNT * _PHOTO_CANDIDATES_PER_VIDEO
_DEFAULT_ANALYSIS_SAMPLE_SIZE = 5
_EVOLINK_MAX_ATTEMPTS = 5
_RUNNING_STATUSES = {
    "pending",
    "video_analyzing",
    "name_generating",
    "photo_generating",
    "avatar_generating",
}

_RESUMABLE_STAGES = {
    "current",
    "video_analyzing",
    "name_generating",
    "photo_generating",
    "avatar_generating",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utcnow_iso() -> str:
    return _utcnow().isoformat()


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


def _new_state(account_id: str, status: str) -> dict[str, Any]:
    return {
        "account_id": account_id,
        "status": status,
        "error_message": "",
        "selected_tag_ids": [],
        "all_video_count": 0,
        "analysis_sample_size": _DEFAULT_ANALYSIS_SAMPLE_SIZE,
        "analysis_video_ids": [],
        "analysis_items": [],
        "video_descriptions": [],
        "combined_description": "",
        "generated_name": "",
        "photo_candidate_count": _PHOTO_CANDIDATE_COUNT,
        "photo_candidates": [],
        "selected_photo_candidate_id": None,
        "generated_avatar_url": "",
        "generated_photo_url": "",
        "completed_stages": [],
        "updated_at": _utcnow_iso(),
    }


_STATE_DEFAULTS = _new_state("", "idle")


def _ensure_state_shape(state: dict[str, Any] | None, account_id: str = "") -> dict[str, Any]:
    state = dict(state or {})
    for key, value in _STATE_DEFAULTS.items():
        if key not in state:
            state[key] = value if not isinstance(value, (list, dict)) else json.loads(json.dumps(value))
    if account_id and not state.get("account_id"):
        state["account_id"] = account_id
    state["selected_tag_ids"] = list(state.get("selected_tag_ids") or [])
    state["analysis_video_ids"] = [str(x) for x in (state.get("analysis_video_ids") or [])]
    state["analysis_items"] = list(state.get("analysis_items") or [])
    state["video_descriptions"] = list(state.get("video_descriptions") or [])
    state["photo_candidates"] = list(state.get("photo_candidates") or [])
    state["completed_stages"] = list(state.get("completed_stages") or [])
    state["selected_photo_candidate_id"] = state.get("selected_photo_candidate_id")
    return state


def _mark_dirty(account_id: str) -> None:
    dirty_ai_account_ids.add(account_id)


def _mark_stage_completed(state: dict[str, Any], stage: str) -> None:
    completed = state.setdefault("completed_stages", [])
    if stage not in completed:
        completed.append(stage)


async def _save_state(account_id: str) -> dict[str, Any]:
    state = _ensure_state_shape(ai_account_states.get(account_id), account_id)
    state["updated_at"] = _utcnow_iso()
    ai_account_states[account_id] = state
    _mark_dirty(account_id)
    await _persist_states([account_id])
    return state


def _set_status(account_id: str, status: str, *, error: str = "") -> None:
    state = _ensure_state_shape(ai_account_states.get(account_id), account_id)
    state["status"] = status
    state["error_message"] = error
    state["updated_at"] = _utcnow_iso()
    ai_account_states[account_id] = state
    _mark_dirty(account_id)


def get_ai_account_state(account_id: str) -> dict[str, Any] | None:
    state = ai_account_states.get(account_id)
    return _ensure_state_shape(state, account_id) if state else None


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
            state = _ensure_state_shape(state, aid)
            ai_account_states[aid] = state
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


async def _restore_state_from_db(account_id: str) -> dict[str, Any] | None:
    if account_id in ai_account_states:
        return _ensure_state_shape(ai_account_states[account_id], account_id)

    from app.models.account import Account

    try:
        uuid_val = UUID(account_id)
    except ValueError:
        return None

    async with SessionLocal() as session:
        acc = await session.get(Account, uuid_val)
        if not acc or not acc.ai_generation_state:
            return None
        state = _ensure_state_shape(acc.ai_generation_state, account_id)
        state["status"] = acc.ai_generation_status or state.get("status") or "idle"
        state["error_message"] = acc.ai_generation_error or state.get("error_message") or ""
        ai_account_states[account_id] = state
        return state


# =============================================================================
# 通用辅助函数
# =============================================================================


def _compact_text(text: str) -> str:
    return " ".join((text or "").replace("```", " ").split())



def _limit_image_prompt_context(text: str, max_chars: int = _IMAGE_PROMPT_MAX_CHARS) -> str:
    compact = _compact_text(text)
    if len(compact) <= max_chars:
        return compact
    truncated = compact[:max_chars].rsplit(" ", 1)[0].strip()
    return truncated or compact[:max_chars]



def _should_retry_image_submit(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError) and 400 <= exc.response.status_code < 500:
        return False
    return True



def _pick_analysis_videos(videos: list[dict[str, str]], sample_size: int) -> list[dict[str, str]]:
    if not videos:
        return []
    if len(videos) <= sample_size:
        return list(videos)
    return random.sample(videos, sample_size)



def _pick_photo_source_videos(videos: list[dict[str, str]], count: int = _PHOTO_SOURCE_VIDEO_COUNT) -> list[dict[str, str]]:
    if not videos:
        return []
    return random.sample(videos, min(count, len(videos)))



def _selected_photo_url(state: dict[str, Any]) -> str:
    candidate_id = state.get("selected_photo_candidate_id")
    if not candidate_id:
        return state.get("generated_photo_url", "")
    for candidate in state.get("photo_candidates", []):
        if candidate.get("candidate_id") == candidate_id:
            return candidate.get("generated_photo_url", "") or state.get("generated_photo_url", "")
    return state.get("generated_photo_url", "")


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

    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return text.strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"Unexpected EvoLink response format: {data}") from exc


# =============================================================================
# Nano2 生图
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
            logger.error("Nano2 image submit error: status=%d, body=%s", resp.status_code, resp.text)
        resp.raise_for_status()
        data = resp.json()
    task_id = data.get("id")
    if not task_id:
        raise ValueError(f"Nano2 image response missing task id: {data}")
    logger.info("Nano2 image task submitted: task_id=%s", task_id)
    return task_id


async def _poll_nano2_task(
    *,
    api_base_url: str,
    api_key: str,
    task_id: str,
) -> str:
    url = f"{api_base_url.rstrip('/')}/v1/tasks/{task_id}"
    deadline = asyncio.get_event_loop().time() + _IMAGEGEN_POLL_TIMEOUT
    while True:
        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {api_key}"})
            resp.raise_for_status()
            data = resp.json()
        task_status = data.get("status")
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
# 各阶段处理函数
# =============================================================================


async def _stage_video_analysis(
    account_id: str,
    analysis_videos: list[dict[str, str]],
    sample_size: int,
    api_base_url: str,
    api_key: str,
    model_name: str,
    prompt: str,
) -> str:
    state = _ensure_state_shape(ai_account_states.get(account_id), account_id)
    if "video_analyzing" in state.get("completed_stages", []) and state.get("combined_description"):
        ai_account_states[account_id] = state
        return state.get("combined_description", "")

    _set_status(account_id, "video_analyzing")
    state = _ensure_state_shape(ai_account_states.get(account_id), account_id)
    state["analysis_sample_size"] = sample_size
    state["analysis_video_ids"] = [video["video_source_id"] for video in analysis_videos]
    state["analysis_items"] = [
        {
            "video_source_id": video["video_source_id"],
            "video_url": video["video_url"],
            "status": "pending",
            "description": "",
            "error_message": "",
        }
        for video in analysis_videos
    ]
    ai_account_states[account_id] = state
    await _save_state(account_id)

    async def _analyze_one(index: int, video: dict[str, str]) -> None:
        state = ai_account_states[account_id]
        state["analysis_items"][index]["status"] = "running"
        state["analysis_items"][index]["error_message"] = ""
        await _save_state(account_id)

        last_exc: Exception | None = None
        description = ""
        for attempt in range(1, 4):
            try:
                description = await _call_evolink_video(
                    api_base_url=api_base_url,
                    api_key=api_key,
                    model_name=model_name,
                    video_url=video["video_url"],
                    prompt=prompt,
                )
                last_exc = None
                break
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "[%s] video analysis attempt %d/3 failed for %s: %s",
                    account_id,
                    attempt,
                    video["video_url"][:60],
                    exc,
                )
        state = ai_account_states[account_id]
        if last_exc is not None:
            state["analysis_items"][index]["status"] = "failed"
            state["analysis_items"][index]["error_message"] = str(last_exc)
        else:
            state["analysis_items"][index]["status"] = "completed"
            state["analysis_items"][index]["description"] = description
        await _save_state(account_id)

    await asyncio.gather(*[_analyze_one(index, video) for index, video in enumerate(analysis_videos)])

    state = ai_account_states[account_id]
    valid_descriptions = [item["description"] for item in state["analysis_items"] if item.get("status") == "completed" and item.get("description")]
    if not valid_descriptions:
        raise ValueError("所有视频分析均失败，无法生成描述")

    state["video_descriptions"] = valid_descriptions
    state["combined_description"] = "\n\n".join(f"```\n{desc}\n```" for desc in valid_descriptions)
    _mark_stage_completed(state, "video_analyzing")
    ai_account_states[account_id] = state
    await _save_state(account_id)
    return state["combined_description"]


async def _stage_name_generation(
    account_id: str,
    combined_description: str,
    api_base_url: str,
    api_key: str,
    model_name: str,
    name_prompt: str,
) -> str:
    state = _ensure_state_shape(ai_account_states.get(account_id), account_id)
    if "name_generating" in state.get("completed_stages", []) and state.get("generated_name"):
        ai_account_states[account_id] = state
        return state.get("generated_name", "")

    _set_status(account_id, "name_generating")
    full_prompt = (
        f"{name_prompt}\n\n参考视频内容描述：\n{combined_description}"
        if name_prompt
        else f"根据以下视频内容描述，为这个博主取一个有吸引力的名字，直接输出名字即可：\n{combined_description}"
    )

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
        raise last_exc

    state = ai_account_states[account_id]
    state["generated_name"] = name
    _mark_stage_completed(state, "name_generating")
    ai_account_states[account_id] = state
    await _save_state(account_id)
    return name


async def _analyze_photo_source(
    *,
    account_id: str,
    source_video_url: str,
    photo_video_prompt: str,
    api_base_url: str,
    api_key: str,
    understand_model: str,
) -> str:
    desc_prompt = photo_video_prompt or "请详细描述视频中人物的外貌特征、肤色、发型、表情、体型等，用于生成写实人物照片。"
    last_exc: Exception | None = None
    description = ""
    for attempt in range(1, 4):
        try:
            description = await _call_evolink_video(
                api_base_url=api_base_url,
                api_key=api_key,
                model_name=understand_model,
                video_url=source_video_url,
                prompt=desc_prompt,
                temperature=1.0,
            )
            last_exc = None
            break
        except Exception as exc:
            last_exc = exc
            logger.warning("[%s] photo source analysis attempt %d/3 failed: %s", account_id, attempt, exc)
    if last_exc is not None:
        raise last_exc
    return description


async def _run_photo_candidate(
    *,
    account_id: str,
    candidate_index: int,
    description: str,
    photo_image_prompt: str,
    api_base_url: str,
    api_key: str,
    avatar_model: str,
    avatar_size: str,
    avatar_quality: str,
) -> None:
    state = ai_account_states[account_id]
    candidate = state["photo_candidates"][candidate_index]
    candidate["status"] = "generating"
    candidate["error_message"] = ""
    candidate["started_at"] = _utcnow_iso()
    candidate["analysis_description"] = description
    await _save_state(account_id)

    limited_description = _limit_image_prompt_context(description)
    image_prompt = f"{photo_image_prompt}\n\n人物描述：{limited_description}" if photo_image_prompt else limited_description
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
            logger.warning("[%s] photo candidate Nano2 attempt %d/3 failed: %s", account_id, attempt, exc)
            if not _should_retry_image_submit(exc):
                break

    state = ai_account_states[account_id]
    candidate = state["photo_candidates"][candidate_index]
    if last_exc is not None:
        candidate["status"] = "failed"
        candidate["error_message"] = str(last_exc)
        candidate["finished_at"] = _utcnow_iso()
        await _save_state(account_id)
        return

    cdn_url = await _upload_remote_image_to_cdn(result_url, f"photo_candidate_{candidate_index + 1}.png")
    candidate["generated_photo_url"] = cdn_url
    candidate["status"] = "completed"
    candidate["finished_at"] = _utcnow_iso()
    await _save_state(account_id)


async def _stage_photo_generation(
    account_id: str,
    all_videos: list[dict[str, str]],
    photo_video_prompt: str,
    photo_image_prompt: str,
    api_base_url: str,
    api_key: str,
    understand_model: str,
    avatar_model: str,
    avatar_size: str,
    avatar_quality: str,
) -> None:
    state = _ensure_state_shape(ai_account_states.get(account_id), account_id)
    if "photo_generating" in state.get("completed_stages", []) and state.get("photo_candidates"):
        ai_account_states[account_id] = state
        return

    _set_status(account_id, "photo_generating")
    source_videos = _pick_photo_source_videos(all_videos)
    if not source_videos:
        raise ValueError("没有可用于生成照片候选的视频")
    state = ai_account_states[account_id]
    photo_candidates: list[dict[str, Any]] = []
    for source_index, video in enumerate(source_videos, start=1):
        for candidate_number in range(1, _PHOTO_CANDIDATES_PER_VIDEO + 1):
            photo_candidates.append(
                {
                    "candidate_id": str(uuid4()),
                    "video_source_id": video["video_source_id"],
                    "video_url": video["video_url"],
                    "source_group_index": source_index,
                    "candidate_number": candidate_number,
                    "status": "pending",
                    "analysis_description": "",
                    "generated_photo_url": "",
                    "error_message": "",
                    "started_at": None,
                    "finished_at": None,
                }
            )
    state["photo_candidate_count"] = len(photo_candidates)
    state["photo_candidates"] = photo_candidates
    ai_account_states[account_id] = state
    await _save_state(account_id)

    async def _run_source_group(source_index: int, video: dict[str, str]) -> None:
        candidate_indexes = [
            index
            for index, candidate in enumerate(ai_account_states[account_id]["photo_candidates"])
            if candidate.get("source_group_index") == source_index
        ]
        for candidate_index in candidate_indexes:
            candidate = ai_account_states[account_id]["photo_candidates"][candidate_index]
            candidate["status"] = "analyzing"
            candidate["error_message"] = ""
            candidate["started_at"] = _utcnow_iso()
        await _save_state(account_id)

        try:
            description = await _analyze_photo_source(
                account_id=account_id,
                source_video_url=video["video_url"],
                photo_video_prompt=photo_video_prompt,
                api_base_url=api_base_url,
                api_key=api_key,
                understand_model=understand_model,
            )
        except Exception as exc:
            for candidate_index in candidate_indexes:
                candidate = ai_account_states[account_id]["photo_candidates"][candidate_index]
                candidate["status"] = "failed"
                candidate["error_message"] = str(exc)
                candidate["finished_at"] = _utcnow_iso()
            await _save_state(account_id)
            return

        for candidate_index in candidate_indexes:
            candidate = ai_account_states[account_id]["photo_candidates"][candidate_index]
            candidate["analysis_description"] = description
            candidate["status"] = "pending"
        await _save_state(account_id)

        await asyncio.gather(
            *[
                _run_photo_candidate(
                    account_id=account_id,
                    candidate_index=candidate_index,
                    description=description,
                    photo_image_prompt=photo_image_prompt,
                    api_base_url=api_base_url,
                    api_key=api_key,
                    avatar_model=avatar_model,
                    avatar_size=avatar_size,
                    avatar_quality=avatar_quality,
                )
                for candidate_index in candidate_indexes
            ]
        )

    await asyncio.gather(
        *[_run_source_group(source_index, video) for source_index, video in enumerate(source_videos, start=1)]
    )

    state = ai_account_states[account_id]
    success_candidates = [candidate for candidate in state["photo_candidates"] if candidate.get("status") == "completed" and candidate.get("generated_photo_url")]
    if not success_candidates:
        raise ValueError("照片候选全部生成失败，无法继续")

    _mark_stage_completed(state, "photo_generating")
    state["selected_photo_candidate_id"] = None
    state["generated_photo_url"] = ""
    ai_account_states[account_id] = state
    _set_status(account_id, "awaiting_photo_selection")
    await _save_state(account_id)


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
    state = _ensure_state_shape(ai_account_states.get(account_id), account_id)
    if "avatar_generating" in state.get("completed_stages", []) and state.get("generated_avatar_url"):
        ai_account_states[account_id] = state
        return state.get("generated_avatar_url", "")

    _set_status(account_id, "avatar_generating")
    prompt_parts: list[str] = []
    if avatar_prompt:
        prompt_parts.append(avatar_prompt)
    else:
        prompt_parts.append("请基于参考照片和以下视频内容描述生成一张博主头像。")
    prompt_parts.append(f"参考视频内容描述：\n{_limit_image_prompt_context(combined_description)}")
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
            result_url = await _poll_nano2_task(api_base_url=api_base_url, api_key=api_key, task_id=task_id)
            last_exc = None
            break
        except Exception as exc:
            last_exc = exc
            logger.warning("[%s] avatar_generating attempt %d/3 failed: %s", account_id, attempt, exc)
            if not _should_retry_image_submit(exc):
                break
    if last_exc is not None:
        raise last_exc

    cdn_url = await _upload_remote_image_to_cdn(result_url, "avatar.png")
    state = ai_account_states[account_id]
    state["generated_avatar_url"] = cdn_url
    _mark_stage_completed(state, "avatar_generating")
    ai_account_states[account_id] = state
    await _save_state(account_id)
    return cdn_url


# =============================================================================
# 主管道
# =============================================================================


async def _run_pipeline(account_id: str, semaphore: asyncio.Semaphore) -> None:
    async with semaphore:
        try:
            from sqlalchemy import select

            from app.models.account import Account
            from app.models.account_tag import AccountTag
            from app.models.tag import VideoSourceTag
            from app.models.video_source import VideoSource
            from app.services.pipeline_settings_service import get_or_create_pipeline_settings
            from app.services.system_settings_service import get_or_create_system_settings

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

                if acc.owner_id is not None:
                    pipeline_cfg = await get_or_create_pipeline_settings(session, owner_id=acc.owner_id)
                    video_prompt = pipeline_cfg.ai_account_video_prompt or "请用中文详细描述这个视频的内容，包括场景、人物特征、服装风格、行为动作等。"
                    video_model = pipeline_cfg.ai_account_video_model or "gemini-3.1-pro-preview"
                    name_prompt = pipeline_cfg.ai_account_name_prompt or ""
                    avatar_prompt = pipeline_cfg.ai_account_avatar_prompt or ""
                    photo_video_prompt = pipeline_cfg.ai_account_photo_video_prompt or ""
                    photo_image_prompt = pipeline_cfg.ai_account_photo_image_prompt or ""
                    name_model = pipeline_cfg.ai_account_name_model or "gemini-3.1-pro-preview"
                    avatar_model = pipeline_cfg.ai_account_avatar_model or "gemini-3.1-flash-image-preview"
                    avatar_size = pipeline_cfg.ai_account_avatar_size or "1:1"
                    avatar_quality = pipeline_cfg.ai_account_avatar_quality or "1K"
                    analysis_sample_size = pipeline_cfg.ai_account_analysis_sample_size or _DEFAULT_ANALYSIS_SAMPLE_SIZE
                else:
                    video_prompt = "请用中文详细描述这个视频的内容，包括场景、人物特征、服装风格、行为动作等。"
                    video_model = "gemini-3.1-pro-preview"
                    name_prompt = ""
                    avatar_prompt = ""
                    photo_video_prompt = ""
                    photo_image_prompt = ""
                    name_model = "gemini-3.1-pro-preview"
                    avatar_model = "gemini-3.1-flash-image-preview"
                    avatar_size = "1:1"
                    avatar_quality = "1K"
                    analysis_sample_size = _DEFAULT_ANALYSIS_SAMPLE_SIZE

                bound_tag_ids = (
                    await session.execute(select(AccountTag.tag_id).where(AccountTag.account_id == acc.id))
                ).scalars().all()
                tag_ids = [str(tag_id) for tag_id in bound_tag_ids]

                state = _ensure_state_shape(ai_account_states.get(account_id), account_id)
                state["selected_tag_ids"] = tag_ids
                state["analysis_sample_size"] = int(analysis_sample_size or _DEFAULT_ANALYSIS_SAMPLE_SIZE)
                ai_account_states[account_id] = state
                _mark_dirty(account_id)

                all_videos: list[dict[str, str]] = []
                if tag_ids:
                    tag_uuid_list = [UUID(tid) for tid in tag_ids]
                    stmt = (
                        select(VideoSource)
                        .join(VideoSourceTag, VideoSourceTag.video_source_id == VideoSource.id)
                        .where(VideoSourceTag.tag_id.in_(tag_uuid_list))
                        .order_by(VideoSource.created_at.desc())
                    )
                    rows = (await session.execute(stmt)).scalars().all()
                    seen: set[str] = set()
                    for vs in rows:
                        video_url = vs.local_video_url or vs.video_url
                        if not video_url:
                            continue
                        video_id = str(vs.id)
                        if video_id in seen:
                            continue
                        seen.add(video_id)
                        all_videos.append({
                            "video_source_id": video_id,
                            "video_url": video_url,
                        })

            if not all_videos:
                raise ValueError("选中的标签没有关联的视频，无法生成博主内容")

            state = ai_account_states[account_id]
            state["all_video_count"] = len(all_videos)
            ai_account_states[account_id] = state
            await _save_state(account_id)

            analysis_videos = _pick_analysis_videos(all_videos, max(1, int(state.get("analysis_sample_size") or _DEFAULT_ANALYSIS_SAMPLE_SIZE)))
            combined_description = await _stage_video_analysis(
                account_id=account_id,
                analysis_videos=analysis_videos,
                sample_size=max(1, int(state.get("analysis_sample_size") or _DEFAULT_ANALYSIS_SAMPLE_SIZE)),
                api_base_url=api_base_url,
                api_key=api_key,
                model_name=video_model,
                prompt=video_prompt,
            )

            await _stage_name_generation(
                account_id=account_id,
                combined_description=combined_description,
                api_base_url=api_base_url,
                api_key=api_key,
                model_name=name_model,
                name_prompt=name_prompt,
            )

            await _stage_photo_generation(
                account_id=account_id,
                all_videos=all_videos,
                photo_video_prompt=photo_video_prompt,
                photo_image_prompt=photo_image_prompt,
                api_base_url=api_base_url,
                api_key=api_key,
                understand_model=video_model,
                avatar_model=avatar_model,
                avatar_size=avatar_size,
                avatar_quality=avatar_quality,
            )

            state = ai_account_states[account_id]
            if not state.get("selected_photo_candidate_id"):
                logger.info("[%s] pipeline paused, awaiting manual photo selection", account_id)
                return

            selected_photo_url = _selected_photo_url(state)
            if not selected_photo_url:
                raise ValueError("已选择的照片候选不存在，无法继续生成头像")

            await _stage_avatar_generation(
                account_id=account_id,
                combined_description=combined_description,
                reference_photo_url=selected_photo_url,
                api_base_url=api_base_url,
                api_key=api_key,
                avatar_model=avatar_model,
                avatar_prompt=avatar_prompt,
                avatar_size=avatar_size,
                avatar_quality=avatar_quality,
            )

            _set_status(account_id, "completed")
            logger.info("[%s] pipeline completed", account_id)
            await _save_state(account_id)

        except asyncio.CancelledError:
            _set_status(account_id, "failed", error="任务被取消")
            await _save_state(account_id)
            raise
        except Exception as exc:
            logger.exception("[%s] pipeline failed: %s", account_id, exc)
            _set_status(account_id, "failed", error=str(exc))
            await _save_state(account_id)
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
    state = _ensure_state_shape(ai_account_states.get(account_id), account_id)
    state["status"] = "pending"
    state["error_message"] = ""
    state["selected_tag_ids"] = tag_ids
    state["all_video_count"] = 0
    state["analysis_video_ids"] = []
    state["analysis_items"] = []
    state["video_descriptions"] = []
    state["combined_description"] = ""
    state["generated_name"] = ""
    state["photo_candidate_count"] = _PHOTO_CANDIDATE_COUNT
    state["photo_candidates"] = []
    state["selected_photo_candidate_id"] = None
    state["generated_avatar_url"] = ""
    state["generated_photo_url"] = ""
    state["completed_stages"] = []
    state["updated_at"] = _utcnow_iso()
    ai_account_states[account_id] = state
    _mark_dirty(account_id)

    _ensure_persist_worker()
    await _persist_states([account_id])
    dirty_ai_account_ids.discard(account_id)
    await ai_account_queue.put(account_id)
    logger.info("[%s] AI account generation enqueued, tag_ids=%s", account_id, tag_ids)


async def _clear_account_generated_assets(
    account_id: str,
    *,
    clear_photo: bool = False,
    clear_avatar: bool = False,
) -> None:
    from app.models.account import Account

    try:
        uuid_val = UUID(account_id)
    except ValueError:
        return

    async with SessionLocal() as session:
        acc = await session.get(Account, uuid_val)
        if not acc:
            return
        if clear_photo:
            acc.photo_url = None
        if clear_avatar:
            acc.avatar_url = None
        await session.commit()


def _prepare_state_for_resume_from_stage(state: dict[str, Any], from_stage: str) -> tuple[dict[str, Any], dict[str, bool]]:
    state = _ensure_state_shape(state, state.get("account_id", ""))
    clear_flags = {"photo": False, "avatar": False}

    if from_stage == "current":
        return state, clear_flags

    if from_stage not in _RESUMABLE_STAGES:
        raise ValueError(f"不支持的恢复阶段: {from_stage}")

    if from_stage == "video_analyzing":
        state["analysis_video_ids"] = []
        state["analysis_items"] = []
        state["video_descriptions"] = []
        state["combined_description"] = ""
        state["generated_name"] = ""
        state["photo_candidate_count"] = _PHOTO_CANDIDATE_COUNT
        state["photo_candidates"] = []
        state["selected_photo_candidate_id"] = None
        state["generated_photo_url"] = ""
        state["generated_avatar_url"] = ""
        state["completed_stages"] = []
        clear_flags["photo"] = True
        clear_flags["avatar"] = True
    elif from_stage == "name_generating":
        state["generated_name"] = ""
        state["photo_candidate_count"] = _PHOTO_CANDIDATE_COUNT
        state["photo_candidates"] = []
        state["selected_photo_candidate_id"] = None
        state["generated_photo_url"] = ""
        state["generated_avatar_url"] = ""
        state["completed_stages"] = [stage for stage in state.get("completed_stages", []) if stage == "video_analyzing"]
        clear_flags["photo"] = True
        clear_flags["avatar"] = True
    elif from_stage == "photo_generating":
        state["photo_candidate_count"] = _PHOTO_CANDIDATE_COUNT
        state["photo_candidates"] = []
        state["selected_photo_candidate_id"] = None
        state["generated_photo_url"] = ""
        state["generated_avatar_url"] = ""
        state["completed_stages"] = [
            stage for stage in state.get("completed_stages", [])
            if stage in {"video_analyzing", "name_generating"}
        ]
        clear_flags["photo"] = True
        clear_flags["avatar"] = True
    elif from_stage == "avatar_generating":
        state["generated_avatar_url"] = ""
        state["completed_stages"] = [
            stage for stage in state.get("completed_stages", [])
            if stage in {"video_analyzing", "name_generating", "photo_generating"}
        ]
        clear_flags["avatar"] = True

    state["status"] = from_stage
    state["error_message"] = ""
    state["updated_at"] = _utcnow_iso()
    return state, clear_flags


async def resume_ai_account_generation(account_id: str, from_stage: str = "current") -> str:
    state = await _restore_state_from_db(account_id)
    if state is None:
        state = _new_state(account_id, "pending")
        ai_account_states[account_id] = state

    existing_task = ai_account_worker_tasks.get(account_id)
    if existing_task is not None and not existing_task.done():
        await _save_state(account_id)
        return "already_running"

    if from_stage == "current" and state.get("status") == "awaiting_photo_selection":
        await _save_state(account_id)
        return "awaiting_photo_selection"

    state, clear_flags = _prepare_state_for_resume_from_stage(state, from_stage)
    state["status"] = "pending"
    ai_account_states[account_id] = state
    _mark_dirty(account_id)

    _ensure_persist_worker()
    await _persist_states([account_id])
    dirty_ai_account_ids.discard(account_id)
    if clear_flags["photo"] or clear_flags["avatar"]:
        await _clear_account_generated_assets(
            account_id,
            clear_photo=clear_flags["photo"],
            clear_avatar=clear_flags["avatar"],
        )
    await ai_account_queue.put(account_id)
    logger.info(
        "[%s] AI account generation resumed from_stage=%s, completed_stages=%s",
        account_id,
        from_stage,
        state.get("completed_stages", []),
    )
    return "resuming"


async def restart_ai_account_generation(account_id: str, tag_ids: list[str] | None = None) -> None:
    if tag_ids is None:
        existing_state = ai_account_states.get(account_id) or await _restore_state_from_db(account_id)
        tag_ids = list((existing_state or {}).get("selected_tag_ids", []) or [])

    state = _ensure_state_shape(ai_account_states.get(account_id), account_id)
    state["status"] = "pending"
    state["error_message"] = ""
    state["selected_tag_ids"] = tag_ids or []
    state["all_video_count"] = 0
    state["analysis_video_ids"] = []
    state["analysis_items"] = []
    state["video_descriptions"] = []
    state["combined_description"] = ""
    state["generated_name"] = ""
    state["photo_candidate_count"] = _PHOTO_CANDIDATE_COUNT
    state["photo_candidates"] = []
    state["selected_photo_candidate_id"] = None
    state["generated_avatar_url"] = ""
    state["generated_photo_url"] = ""
    state["completed_stages"] = []
    state["updated_at"] = _utcnow_iso()
    ai_account_states[account_id] = state
    _mark_dirty(account_id)

    _ensure_persist_worker()
    await _persist_states([account_id])
    dirty_ai_account_ids.discard(account_id)
    await ai_account_queue.put(account_id)
    logger.info("[%s] AI account generation restarted from scratch, tag_ids=%s", account_id, tag_ids)


async def select_ai_account_photo_candidate(account_id: str, candidate_id: str) -> dict[str, Any]:
    state = await _restore_state_from_db(account_id)
    if state is None:
        raise ValueError("未找到 AI 生成状态")
    if state.get("status") != "awaiting_photo_selection":
        raise ValueError("当前状态不支持选择照片候选")

    matched = None
    for candidate in state.get("photo_candidates", []):
        if candidate.get("candidate_id") == candidate_id:
            matched = candidate
            break
    if not matched or matched.get("status") != "completed" or not matched.get("generated_photo_url"):
        raise ValueError("所选照片候选不存在或尚未生成成功")

    state["selected_photo_candidate_id"] = candidate_id
    state["generated_photo_url"] = matched["generated_photo_url"]
    state["error_message"] = ""
    state["status"] = "pending"
    state["updated_at"] = _utcnow_iso()
    ai_account_states[account_id] = state
    _mark_dirty(account_id)

    _ensure_persist_worker()
    await _persist_states([account_id])
    dirty_ai_account_ids.discard(account_id)
    await ai_account_queue.put(account_id)
    logger.info("[%s] selected photo candidate %s and re-enqueued avatar generation", account_id, candidate_id)
    return state



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
    from sqlalchemy import select

    from app.models.account import Account

    async with SessionLocal() as session:
        stuck_statuses = list(_RUNNING_STATUSES)
        stmt = (
            select(Account)
            .where(Account.ai_generation_status.in_(stuck_statuses))
            .where(Account.ai_generation_error.is_(None))
        )
        accounts = (await session.execute(stmt)).scalars().all()

        for acc in accounts:
            account_id = str(acc.id)
            state = _ensure_state_shape(acc.ai_generation_state, account_id)
            state["status"] = acc.ai_generation_status or state.get("status") or "pending"
            ai_account_states[account_id] = state
            _mark_dirty(account_id)
            await ai_account_queue.put(account_id)
            logger.info("[%s] Recovered stuck account on startup: status=%s", account_id, acc.ai_generation_status)

    if accounts:
        await _persist_states([str(acc.id) for acc in accounts])
