from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

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
_PHOTO_CANDIDATE_COUNT = 5
_DEFAULT_ANALYSIS_SAMPLE_SIZE = 5
_AI_API_MAX_ATTEMPTS = 5
_RUNNING_STATUSES = {
    "pending",
    "video_analyzing",
    "name_generating",
    "photo_generating",
    "avatar_generating",
}

_RESUMABLE_STAGES = {
    "current",
    "photo_generating",
    "video_analyzing",
    "name_generating",
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


async def _upload_image_bytes_to_cdn(img_bytes: bytes, filename: str) -> str:
    """Upload raw image bytes directly to our CDN, returning the CDN URL."""
    from app.services.upload_service import UpstreamImageUploadService, detect_image_content_type
    import os
    content_type, ext = detect_image_content_type(img_bytes)
    base = os.path.splitext(filename)[0]
    actual_filename = base + ext
    svc = UpstreamImageUploadService()
    upload_result = await svc.upload_image(img_bytes, content_type, actual_filename)
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
        "generated_handle": "",
        "generated_signature": "",
        "generated_gender": "",
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


async def _unique_account_name(
    session: "AsyncSession",
    base_name: str,
    owner_id: "UUID | None",
    exclude_id: "UUID | None" = None,
) -> str:
    """返回同 owner 下不重复的账号名。若 base_name 已存在则追加 -1、-2 …"""
    from sqlalchemy import select
    from app.models.account import Account

    base_name = base_name[:200]
    candidate = base_name
    suffix = 1
    while True:
        stmt = select(Account.id).where(Account.account_name == candidate)
        if owner_id is not None:
            stmt = stmt.where(Account.owner_id == owner_id)
        if exclude_id is not None:
            stmt = stmt.where(Account.id != exclude_id)
        stmt = stmt.limit(1)
        if not (await session.scalar(stmt)):
            return candidate
        suffix_token = f"-{suffix}"
        candidate = f"{base_name[:200 - len(suffix_token)]}{suffix_token}"
        suffix += 1


async def _unique_account_handle(
    session: "AsyncSession",
    base_handle: str,
    owner_id: "UUID | None",
    exclude_id: "UUID | None" = None,
) -> str:
    """返回同 owner 下不重复的 handle。若 base_handle 已存在则追加 _1、_2 …"""
    from sqlalchemy import select
    from app.models.account import Account

    base_handle = base_handle[:200]
    candidate = base_handle
    suffix = 1
    while True:
        stmt = select(Account.id).where(Account.account_handle == candidate)
        if owner_id is not None:
            stmt = stmt.where(Account.owner_id == owner_id)
        if exclude_id is not None:
            stmt = stmt.where(Account.id != exclude_id)
        stmt = stmt.limit(1)
        if not (await session.scalar(stmt)):
            return candidate
        suffix_token = f"_{suffix}"
        candidate = f"{base_handle[:200 - len(suffix_token)]}{suffix_token}"
        suffix += 1


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
                unique_name = await _unique_account_name(
                    session,
                    state["generated_name"],
                    owner_id=acc.owner_id,
                    exclude_id=acc.id,
                )
                state["generated_name"] = unique_name
                acc.account_name = unique_name
            if state.get("generated_handle"):
                unique_handle = await _unique_account_handle(
                    session,
                    state["generated_handle"],
                    owner_id=acc.owner_id,
                    exclude_id=acc.id,
                )
                state["generated_handle"] = unique_handle
                acc.account_handle = unique_handle
            if state.get("generated_signature"):
                acc.account_signature = state["generated_signature"]
            if state.get("generated_gender"):
                acc.gender = state["generated_gender"]
            if state.get("generated_avatar_url"):
                acc.avatar_url = state["generated_avatar_url"]
            if state.get("generated_photo_url"):
                acc.photo_url = state["generated_photo_url"]
            acc.ai_generation_state = state
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



def _selected_photo_url(state: dict[str, Any]) -> str:
    candidate_id = state.get("selected_photo_candidate_id")
    if not candidate_id:
        return state.get("generated_photo_url", "")
    for candidate in state.get("photo_candidates", []):
        if candidate.get("candidate_id") == candidate_id:
            return candidate.get("generated_photo_url", "") or state.get("generated_photo_url", "")
    return state.get("generated_photo_url", "")


# =============================================================================
# Gemini REST API 调用（纯文本，无视频）
# =============================================================================


async def _call_gemini_text(
    *,
    model_name: str,
    prompt: str,
    temperature: float = 0.7,
) -> str:
    from app.services.ai_api import call_gemini_api
    return await call_gemini_api(
        model_name=model_name,
        prompt=prompt,
        temperature=temperature,
    )


async def _call_gemini_video(
    *,
    model_name: str,
    video_url: str,
    prompt: str,
    temperature: float = 0.3,
) -> str:
    from app.services.ai_api import call_gemini_api
    return await call_gemini_api(
        model_name=model_name,
        video_url=video_url,
        prompt=prompt,
        temperature=temperature,
    )


# =============================================================================
# Nano2 生图
# =============================================================================


async def _generate_avatar_image(
    *,
    prompt: str,
    model: str,
    size: str,
    quality: str,
    image_urls: list[str] | None = None,
) -> bytes:
    """
    生成头像图片，返回图片 bytes。
    """
    from app.services.ai_api import generate_image
    return await generate_image(
        model_name=model,
        prompt=prompt,
        image_urls=image_urls or [],
        aspect_ratio=size,
        image_size=quality,
    )


# =============================================================================
# 各阶段处理函数
# =============================================================================


async def _stage_video_analysis(
    account_id: str,
    analysis_videos: list[dict[str, str]],
    sample_size: int,
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
                description = await _call_gemini_video(
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
    avatar_url: str,
    photo_url: str,
) -> dict[str, str]:
    state = _ensure_state_shape(ai_account_states.get(account_id), account_id)
    if (
        "name_generating" in state.get("completed_stages", [])
        and state.get("generated_name")
        and state.get("generated_handle")
        and state.get("generated_gender")
    ):
        ai_account_states[account_id] = state
        return {
            "name": state.get("generated_name", ""),
            "handle": state.get("generated_handle", ""),
            "signature": state.get("generated_signature", ""),
            "gender": state.get("generated_gender", ""),
        }

    _set_status(account_id, "name_generating")

    from app.services.name_handle_service import generate_name_handle_for_account

    result = await generate_name_handle_for_account(
        account_id,
        avatar_url=avatar_url,
        photo_url=photo_url,
    )
    if not result or not result.get("name") or not result.get("handle") or not result.get("gender"):
        raise ValueError("名称/handle/性别生成失败，无法完成 AI 博主生成")

    state = ai_account_states[account_id]
    state["generated_name"] = result.get("name", "")
    state["generated_handle"] = result.get("handle", "")
    state["generated_signature"] = result.get("signature", "")
    state["generated_gender"] = result.get("gender", "")
    _mark_stage_completed(state, "name_generating")
    ai_account_states[account_id] = state
    await _save_state(account_id)
    return result


async def _run_photo_candidate(
    *,
    account_id: str,
    candidate_index: int,
    description: str,
    photo_image_prompt: str,
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
    img_bytes: bytes = b""
    last_exc: Exception | None = None
    for attempt in range(1, 4):
        try:
            img_bytes = await _generate_avatar_image(
                prompt=image_prompt,
                model=avatar_model,
                size=avatar_size,
                quality=avatar_quality,
            )
            last_exc = None
            break
        except Exception as exc:
            last_exc = exc
            logger.warning("[%s] photo candidate image gen attempt %d/3 failed: %s", account_id, attempt, exc)
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

    cdn_url = await _upload_image_bytes_to_cdn(img_bytes, f"photo_candidate_{candidate_index + 1}.png")
    candidate["generated_photo_url"] = cdn_url
    candidate["status"] = "completed"
    candidate["finished_at"] = _utcnow_iso()
    await _save_state(account_id)


async def _stage_photo_generation(
    account_id: str,
    tag_ids: list[str],
    owner_id: UUID | None,
    photo_image_prompt: str,
    avatar_model: str,
    avatar_size: str,
    avatar_quality: str,
) -> None:
    """基于人脸库生成照片候选：取当前标签人脸 + 另一个标签人脸，并发生成 5 张候选。"""
    from sqlalchemy import func, select
    from app.models.face_photo import FacePhoto

    state = _ensure_state_shape(ai_account_states.get(account_id), account_id)
    if "photo_generating" in state.get("completed_stages", []) and state.get("photo_candidates"):
        ai_account_states[account_id] = state
        return

    _set_status(account_id, "photo_generating")

    # 1. 取第一个标签的人脸
    first_tag_id = UUID(tag_ids[0]) if tag_ids else None
    if not first_tag_id:
        raise ValueError("博主没有绑定标签，无法生成照片")

    async with SessionLocal() as session:
        primary_face = await session.scalar(
            select(FacePhoto)
            .where(FacePhoto.tag_id == first_tag_id)
            .order_by(FacePhoto.created_at.desc())
            .limit(1)
        )
        if not primary_face or not primary_face.face_photo_url:
            raise ValueError("当前标签没有人脸照片，请先执行人脸选择")

        # 2. 同一 owner 下、不同标签的随机一张人脸
        other_face_stmt = (
            select(FacePhoto)
            .where(FacePhoto.tag_id != first_tag_id)
        )
        if owner_id is not None:
            other_face_stmt = other_face_stmt.where(FacePhoto.owner_id == owner_id)
        other_face_stmt = other_face_stmt.order_by(func.random()).limit(1)
        other_face = await session.scalar(other_face_stmt)

    primary_face_url = primary_face.face_photo_url
    other_face_url = other_face.face_photo_url if other_face else None

    face_image_urls = [primary_face_url]
    if other_face_url:
        face_image_urls.append(other_face_url)

    logger.info("[%s] photo generation using %d face images: primary=%s, other=%s",
                account_id, len(face_image_urls), primary_face_url[:80], (other_face_url or "N/A")[:80])

    # 3. 创建 5 个候选
    state = ai_account_states[account_id]
    photo_candidates: list[dict[str, Any]] = []
    for i in range(1, _PHOTO_CANDIDATE_COUNT + 1):
        photo_candidates.append({
            "candidate_id": str(uuid4()),
            "candidate_number": i,
            "status": "pending",
            "generated_photo_url": "",
            "error_message": "",
            "started_at": None,
            "finished_at": None,
        })
    state["photo_candidate_count"] = len(photo_candidates)
    state["photo_candidates"] = photo_candidates
    ai_account_states[account_id] = state
    await _save_state(account_id)

    # 4. 并发生成 5 张
    async def _gen_one(candidate_index: int) -> None:
        st = ai_account_states[account_id]
        candidate = st["photo_candidates"][candidate_index]
        candidate["status"] = "generating"
        candidate["started_at"] = _utcnow_iso()
        await _save_state(account_id)

        image_prompt = photo_image_prompt or "请基于提供的人脸参考照片生成一张高质量写实人物照片。"
        last_exc: Exception | None = None
        img_bytes: bytes = b""
        for attempt in range(1, 4):
            try:
                img_bytes = await _generate_avatar_image(
                    prompt=image_prompt,
                    model=avatar_model,
                    size=avatar_size,
                    quality=avatar_quality,
                    image_urls=face_image_urls,
                )
                last_exc = None
                break
            except Exception as exc:
                last_exc = exc
                logger.warning("[%s] photo candidate %d attempt %d/3 failed: %s",
                               account_id, candidate_index + 1, attempt, exc)
                if not _should_retry_image_submit(exc):
                    break

        st = ai_account_states[account_id]
        candidate = st["photo_candidates"][candidate_index]
        if last_exc is not None:
            candidate["status"] = "failed"
            candidate["error_message"] = str(last_exc)
            candidate["finished_at"] = _utcnow_iso()
            await _save_state(account_id)
            return

        cdn_url = await _upload_image_bytes_to_cdn(img_bytes, f"photo_candidate_{candidate_index + 1}.png")
        candidate["generated_photo_url"] = cdn_url
        candidate["status"] = "completed"
        candidate["finished_at"] = _utcnow_iso()
        await _save_state(account_id)

    await asyncio.gather(*[_gen_one(i) for i in range(_PHOTO_CANDIDATE_COUNT)])

    state = ai_account_states[account_id]
    success_candidates = [c for c in state["photo_candidates"] if c.get("status") == "completed" and c.get("generated_photo_url")]
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
    img_bytes: bytes = b""
    for attempt in range(1, 4):
        try:
            img_bytes = await _generate_avatar_image(
                prompt=full_prompt,
                model=avatar_model,
                size=avatar_size,
                quality=avatar_quality,
                image_urls=[reference_photo_url] if reference_photo_url else None,
            )
            last_exc = None
            break
        except Exception as exc:
            last_exc = exc
            logger.warning("[%s] avatar_generating attempt %d/3 failed: %s", account_id, attempt, exc)
            if not _should_retry_image_submit(exc):
                break
    if last_exc is not None:
        raise last_exc

    cdn_url = await _upload_image_bytes_to_cdn(img_bytes, "avatar.png")
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
            from app.services.google_api import get_google_api_key

            async with SessionLocal() as session:
                try:
                    uuid_val = UUID(account_id)
                except ValueError:
                    return
                acc = await session.get(Account, uuid_val)
                if not acc:
                    logger.warning("[%s] Account not found", account_id)
                    return

                if not get_google_api_key():
                    raise ValueError("GOOGLE_API_KEY 未配置，请在 .env 中设置。")

                if acc.owner_id is not None:
                    pipeline_cfg = await get_or_create_pipeline_settings(session, owner_id=acc.owner_id)
                    video_prompt = pipeline_cfg.ai_account_video_prompt or "请用中文详细描述这个视频的内容，包括场景、人物特征、服装风格、行为动作等。"
                    video_model = pipeline_cfg.ai_account_video_model or "gemini-3.1-pro-preview"
                    avatar_prompt = pipeline_cfg.ai_account_avatar_prompt or ""
                    photo_image_prompt = pipeline_cfg.ai_account_photo_image_prompt or ""
                    avatar_model = pipeline_cfg.ai_account_avatar_model or "gemini-3.1-flash-image-preview"
                    avatar_size = pipeline_cfg.ai_account_avatar_size or "1:1"
                    avatar_quality = pipeline_cfg.ai_account_avatar_quality or "1K"
                    analysis_sample_size = pipeline_cfg.ai_account_analysis_sample_size or _DEFAULT_ANALYSIS_SAMPLE_SIZE
                else:
                    video_prompt = "请用中文详细描述这个视频的内容，包括场景、人物特征、服装风格、行为动作等。"
                    video_model = "gemini-3.1-pro-preview"
                    avatar_prompt = ""
                    photo_image_prompt = ""
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

            await _stage_photo_generation(
                account_id=account_id,
                tag_ids=tag_ids,
                owner_id=acc.owner_id,
                photo_image_prompt=photo_image_prompt,
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

            analysis_videos = _pick_analysis_videos(all_videos, max(1, int(state.get("analysis_sample_size") or _DEFAULT_ANALYSIS_SAMPLE_SIZE)))
            combined_description = await _stage_video_analysis(
                account_id=account_id,
                analysis_videos=analysis_videos,
                sample_size=max(1, int(state.get("analysis_sample_size") or _DEFAULT_ANALYSIS_SAMPLE_SIZE)),
                model_name=video_model,
                prompt=video_prompt,
            )

            avatar_url = await _stage_avatar_generation(
                account_id=account_id,
                combined_description=combined_description,
                reference_photo_url=selected_photo_url,
                avatar_model=avatar_model,
                avatar_prompt=avatar_prompt,
                avatar_size=avatar_size,
                avatar_quality=avatar_quality,
            )

            await _stage_name_generation(
                account_id=account_id,
                avatar_url=avatar_url,
                photo_url=selected_photo_url,
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
    state["generated_handle"] = ""
    state["generated_signature"] = ""
    state["generated_gender"] = ""
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


def _clear_generated_identity(state: dict[str, Any]) -> None:
    state["generated_name"] = ""
    state["generated_handle"] = ""
    state["generated_signature"] = ""
    state["generated_gender"] = ""


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
        _clear_generated_identity(state)
        state["generated_avatar_url"] = ""
        state["completed_stages"] = [
            stage for stage in state.get("completed_stages", [])
            if stage == "photo_generating"
        ]
        clear_flags["avatar"] = True
    elif from_stage == "name_generating":
        _clear_generated_identity(state)
        state["completed_stages"] = [
            stage for stage in state.get("completed_stages", [])
            if stage in {"photo_generating", "video_analyzing", "avatar_generating"}
        ]
    elif from_stage == "photo_generating":
        _clear_generated_identity(state)
        state["photo_candidate_count"] = _PHOTO_CANDIDATE_COUNT
        state["photo_candidates"] = []
        state["selected_photo_candidate_id"] = None
        state["generated_photo_url"] = ""
        state["generated_avatar_url"] = ""
        state["completed_stages"] = [
            stage for stage in state.get("completed_stages", [])
            if stage == "video_analyzing"
        ]
        clear_flags["photo"] = True
        clear_flags["avatar"] = True
    elif from_stage == "avatar_generating":
        _clear_generated_identity(state)
        state["generated_avatar_url"] = ""
        state["completed_stages"] = [
            stage for stage in state.get("completed_stages", [])
            if stage in {"photo_generating", "video_analyzing"}
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
    state["generated_handle"] = ""
    state["generated_signature"] = ""
    state["generated_gender"] = ""
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
