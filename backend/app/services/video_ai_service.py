from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from uuid import UUID

import httpx

from app.core.config import settings
from app.services.ai_api import call_gemini_api
from app.db.session import SessionLocal
from app.models.enums import VideoAIProcessStatus
from app.models.video_ai_template import VideoAITemplate
from app.services.ext_product_service import enrich_shot_with_ext_products

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
# pipeline 完成后需要同步 shots 到 video_tasks 的模板 ID 集合
_sync_shots_on_success: set[str] = set()

# 队列处理器任务和持久化任务
_queue_processor_task: asyncio.Task | None = None
_persist_worker_task: asyncio.Task | None = None
# 进程关停标志：True 时管道被取消不写 paused，保留运行中状态以便重启后续跑
_shutting_down: bool = False

# 并发数：同时处理的最大任务数
_CONCURRENCY = 5
# 持久化间隔：每 2 秒持久化一次脏数据到数据库
_PERSIST_INTERVAL = 2.0
_PRODUCT_SEARCH_STAGE = "product_search"
_PRODUCT_SEARCH_CONCURRENCY = 4


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
        "completed_stages": [],  # 已完成的阶段列表，用于断点续跑
        "updated_at": _utcnow_iso(),
    }


def _remove_completed_stage(state: dict, stage: str) -> bool:
    completed_stages = state.get("completed_stages") or []
    if stage not in completed_stages:
        return False
    state["completed_stages"] = [s for s in completed_stages if s != stage]
    return True


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
# 抽帧 & 生图辅助
# =============================================================================

_MAX_VIDEO_SECONDS = 15.0   # 超过此时长只取前 15s
_FRAME_INTERVAL = 1.5       # 每隔 1.5s 取一帧
_MAX_FRAMES = 10            # 最多 10 帧（15 / 1.5 = 10，尾帧抛弃）

_IMAGEGEN_POLL_INTERVAL = 5.0    # 轮询间隔（秒）
_IMAGEGEN_POLL_TIMEOUT = 500.0   # 最长等待时间（秒）


async def _extract_frames(video_url: str, template_id: str) -> list[str]:
    """抽帧（使用默认 1.5s 间隔，保持向后兼容）。"""
    return await _extract_frames_with_interval(video_url, template_id, interval=_FRAME_INTERVAL)


async def _extract_frames_with_interval(video_url: str, template_id: str, *, interval: float = 1.0) -> list[str]:
    """
    从视频 URL 抽帧，返回帧图片的 base64 data URL 列表（image/jpeg）。
    超过 15s 的视频只截取前 15s，按 interval 秒抽一帧，抛弃尾帧。
    使用 ffmpeg 命令行完成：先下载视频到临时文件，再抽帧。
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = os.path.join(tmpdir, "video.mp4")

        # 1. 下载视频（流式，限速以免 OOM）
        logger.info("[%s] Downloading video for frame extraction: %s", template_id, video_url[:80])
        async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as client:
            async with client.stream("GET", video_url) as resp:
                resp.raise_for_status()
                with open(video_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(65536):
                        f.write(chunk)

        # 2. 用 ffprobe 获取视频时长
        probe_proc = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", video_path,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        probe_out, _ = await probe_proc.communicate()
        try:
            duration = float(probe_out.decode().strip())
        except ValueError:
            duration = _MAX_VIDEO_SECONDS
        effective_duration = min(duration, _MAX_VIDEO_SECONDS)
        logger.info("[%s] Video duration=%.1fs, effective=%.1fs", template_id, duration, effective_duration)

        # 3. 计算帧时间戳：0, interval, 2*interval … 抛弃尾帧（确保时间戳 < effective_duration）
        max_frames = max(1, int(effective_duration / interval) + 1)
        timestamps = []
        t = 0.0
        while t < effective_duration and len(timestamps) < max_frames:
            timestamps.append(t)
            t += interval
        logger.info("[%s] Extracting %d frames at timestamps: %s", template_id, len(timestamps), timestamps)

        # 4. 用 ffmpeg 批量抽帧
        file_size = os.path.getsize(video_path) if os.path.exists(video_path) else 0
        logger.info("[%s] Downloaded video file size: %d bytes", template_id, file_size)

        frames_dir = os.path.join(tmpdir, "frames")
        os.makedirs(frames_dir, exist_ok=True)

        frame_paths = []
        for i, ts in enumerate(timestamps):
            frame_path = os.path.join(frames_dir, f"frame_{i:03d}.jpg")
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-ss", str(ts), "-i", video_path,
                "-vframes", "1", "-q:v", "3", frame_path,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            _, stderr_data = await proc.communicate()
            if os.path.exists(frame_path) and os.path.getsize(frame_path) > 0:
                frame_paths.append(frame_path)
            else:
                stderr_text = stderr_data.decode(errors="replace")[-300:] if stderr_data else ""
                logger.warning("[%s] Frame at t=%.1fs failed to extract, ffmpeg stderr: %s", template_id, ts, stderr_text)

        # 5. 读取帧为 GCS 可上传的临时 URL（这里返回 base64 data URL 供后续上传）
        data_urls = []
        for fp in frame_paths:
            with open(fp, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            data_urls.append(f"data:image/jpeg;base64,{b64}")

        logger.info("[%s] Extracted %d frames successfully", template_id, len(data_urls))
        return data_urls


async def _upload_frame_to_cdn(data_url: str) -> str:
    """
    将 base64 data URL 的帧图片上传到 CDN，返回公网 URL。
    使用 upload_service 上传。
    """
    from app.services.upload_service import UpstreamImageUploadService
    header, b64data = data_url.split(",", 1)
    content = base64.b64decode(b64data)
    svc = UpstreamImageUploadService()
    result = await svc.upload_image(content, "image/jpeg", "frame.jpg")
    return result.url


_FRAME_INTERVAL_NEW = 1.0  # 新流程：每 1s 一帧


async def _run_imagegen_stage(
    *,
    template_id: str,
    video_url: str,
) -> list[dict]:
    """
    第二阶段：1s抽一帧 → 并发上传 CDN。
    返回 frame_shots 列表，每项格式：{"image_url": str, "frame_index": int}
    """
    # 1. 抽帧（1s 间隔）
    frame_data_urls = await _extract_frames_with_interval(video_url, template_id, interval=_FRAME_INTERVAL_NEW)
    if not frame_data_urls:
        raise ValueError("视频抽帧失败，未获取到任何帧图片")

    # 2. 并发上传所有帧到 CDN
    logger.info("[%s] Uploading %d frames to CDN", template_id, len(frame_data_urls))
    upload_results = await asyncio.gather(
        *[_upload_frame_to_cdn(du) for du in frame_data_urls],
        return_exceptions=True,
    )
    frame_shots = []
    for i, r in enumerate(upload_results):
        if isinstance(r, Exception):
            logger.warning("[%s] Frame %d upload failed: %s", template_id, i, r)
        else:
            frame_shots.append({"image_url": r, "frame_index": i})

    if not frame_shots:
        raise ValueError("所有帧上传 CDN 失败")
    logger.info("[%s] Imagegen stage done: %d frames uploaded to CDN", template_id, len(frame_shots))
    return frame_shots


# JSON schema for outfit selection response
_OUTFIT_SELECT_SCHEMA = {
    "type": "object",
    "properties": {
        "outfits": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "representative_frame_index": {"type": "integer"},
                    "frame_indices": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                },
                "required": ["representative_frame_index", "frame_indices"],
            },
        },
    },
    "required": ["outfits"],
}

# JSON schema for outfit detail (single outfit)
_OUTFIT_DETAIL_SCHEMA = {
    "type": "object",
    "properties": {
        "outfit_style": {"type": "string"},
        "solo_products": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["name", "description"],
            },
        },
    },
    "required": ["outfit_style", "solo_products"],
}


# 意图识别（intent_classify）相关常量
ALLOWED_INTENTS = {"beauty_show", "knowledge", "persona_story", "trend_meme"}

INTENT_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "outfit_ref_images_text": {"type": "string"},
        "content_intent": {"type": "string", "enum": list(ALLOWED_INTENTS)},
        "format_subtype": {"type": "string"},
        "content_intent_secondary": {"type": "string"},
        "video_type": {"type": "string"},
        "cross_cutting": {
            "type": "object",
            "properties": {
                "character": {"type": "string"},
                "motion": {"type": "string"},
                "environment": {"type": "string"},
                "camera": {"type": "string"},
                "audio_and_on_screen_text": {"type": "string"},
            },
        },
        "key_points": {"type": "array", "items": {"type": "string"}},
        "avoid": {"type": "array", "items": {"type": "string"}},
        "reasoning": {"type": "string"},
        "information_core": {
            "type": "object",
            "properties": {
                "problem_or_question": {"type": "string"},
                "steps_or_reasoning": {"type": "array", "items": {"type": "string"}},
                "conclusion_or_takeaway": {"type": "string"},
                "visual_support": {"type": "string"},
            },
        },
        "narrative_beats": {"type": "object"},
        "trend_packaging": {"type": "object"},
    },
    "required": ["content_intent"],
}

DEFAULT_INTENT_PROMPT = (
    "请分析这段视频，结合下面给出的穿搭单品列表（按造型分组的 JSON），判断视频的核心创作意图，"
    "以严格符合 JSON Schema 的结构化数据返回。content_intent 必须从以下四个枚举值中选一："
    "beauty_show（穿搭/美感展示）、knowledge（知识/讲解）、persona_story（人物/故事）、trend_meme（潮流/梗）。\n\n"
    "穿搭单品列表（JSON）：\n{solo_products}\n\n"
    "请直接输出 JSON，不要附加任何额外文字。"
)

DEFAULT_UNDERSTAND_PROMPTS = {
    "beauty_show": (
        "你是穿搭/美感类视频的创作分析师。基于下面给出的意图识别 JSON 与视频本身，"
        "撰写一段用于后续视频生成的提示词描述，覆盖人物气质、动作节奏、环境氛围、镜头语言、关键卖点等。\n\n"
        "意图识别 JSON：\n{intent_json}\n\n"
        "请直接输出最终提示词文本，不要 JSON。"
    ),
    "knowledge": (
        "你是知识/讲解类视频的创作分析师。基于下面给出的意图识别 JSON 与视频本身，"
        "撰写一段用于后续视频生成的提示词描述，覆盖核心问题/结论、讲解步骤、可视化支撑、镜头语言。\n\n"
        "意图识别 JSON：\n{intent_json}\n\n"
        "请直接输出最终提示词文本，不要 JSON。"
    ),
    "persona_story": (
        "你是人物/故事类视频的创作分析师。基于下面给出的意图识别 JSON 与视频本身，"
        "撰写一段用于后续视频生成的提示词描述，覆盖人物设定、情节节拍、情绪走向、镜头语言。\n\n"
        "意图识别 JSON：\n{intent_json}\n\n"
        "请直接输出最终提示词文本，不要 JSON。"
    ),
    "trend_meme": (
        "你是潮流/梗类视频的创作分析师。基于下面给出的意图识别 JSON 与视频本身，"
        "撰写一段用于后续视频生成的提示词描述，覆盖梗的核心、潮流元素、节奏卖点、镜头语言。\n\n"
        "意图识别 JSON：\n{intent_json}\n\n"
        "请直接输出最终提示词文本，不要 JSON。"
    ),
}


def _format_solo_products_for_prompt(outfit_details: list[dict]) -> str:
    """把每套造型的 outfit_style + solo_products 聚合成 JSON 字符串注入 prompt。"""
    payload = []
    for idx, detail in enumerate(outfit_details, start=1):
        payload.append({
            "index": idx,
            "outfit_style": detail.get("outfit_style", ""),
            "solo_products": [
                {"name": p.get("name", ""), "description": p.get("description", "")}
                for p in (detail.get("solo_products") or [])
            ],
        })
    return json.dumps(payload, ensure_ascii=False)


async def _run_intent_classify_stage(
    *,
    template_id: str,
    video_url: str,
    outfit_details: list[dict],
    model: str,
    prompt: str,
    temperature: float,
) -> dict:
    """意图识别：调用 Gemini，输入视频 + solo_products JSON，要求返回结构化 JSON；
    校验 content_intent，最多 3 次重试。
    """
    base_prompt = prompt.strip() if (prompt and prompt.strip()) else DEFAULT_INTENT_PROMPT
    actual_prompt = base_prompt.replace("{solo_products}", _format_solo_products_for_prompt(outfit_details))

    last_exc: Exception | None = None
    for attempt in range(1, 4):
        try:
            raw = await call_gemini_api(
                model_name=model,
                prompt=actual_prompt,
                video_url=video_url,
                temperature=temperature,
                response_schema=INTENT_JSON_SCHEMA,
            )
            data = json.loads(raw)
            intent = data.get("content_intent")
            if intent in ALLOWED_INTENTS:
                logger.info("[%s] intent_classify done, content_intent=%s", template_id, intent)
                return data
            raise ValueError(f"content_intent invalid: {intent!r}")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            last_exc = exc
            delay = min(attempt * 2, 30)
            logger.warning("[%s] intent_classify attempt %d/3 failed: %s", template_id, attempt, exc)
            if attempt < 3:
                await asyncio.sleep(delay)
    raise ValueError(f"intent_classify failed after 3 attempts: {last_exc}") from last_exc


async def _run_understanding_stage(
    *,
    template_id: str,
    video_url: str,
    intent_json: dict,
    model: str,
    temperature: float,
    prompts_by_intent: dict[str, str],
) -> str:
    """根据意图选 prompt → 注入 intent_json → 调 Gemini → 返回纯文本。"""
    intent = intent_json.get("content_intent")
    if intent not in ALLOWED_INTENTS:
        raise ValueError(f"understanding stage got invalid intent: {intent!r}")
    template = (prompts_by_intent.get(intent) or "").strip() or DEFAULT_UNDERSTAND_PROMPTS[intent]
    final_prompt = template.replace("{intent_json}", json.dumps(intent_json, ensure_ascii=False))
    text = await call_gemini_api(
        model_name=model,
        prompt=final_prompt,
        video_url=video_url,
        temperature=temperature,
    )
    logger.info("[%s] understanding done, intent=%s, prompt_description=%d chars",
                template_id, intent, len(text or ""))
    return text


async def _run_outfit_selecting_stage(
    *,
    template_id: str,
    frame_shots: list[dict],
    model: str,
    prompt: str,
    temperature: float,
) -> list[dict]:
    """
    阶段3：将所有帧图发给 Gemini，识别 unique 穿搭并选出代表帧。
    返回 outfit_shots 列表，每项：{"image_url": str, "frame_index": int, "group_frame_indices": [int]}
    """
    from app.services.ai_api import call_gemini_api_with_images

    if not frame_shots:
        raise ValueError("没有帧图片，无法进行穿搭识别")

    frame_urls = [s["image_url"] for s in frame_shots]
    url_to_index = {s["image_url"]: s["frame_index"] for s in frame_shots}

    default_prompt = (
        "以下是从视频中1秒一帧抽取的图片，请识别其中的独特穿搭（outfit）。"
        "不同镜头角度的同一套穿搭算同一个，只选出一张最能代表该穿搭的图。"
        "请以JSON格式输出，其中 representative_frame_index 为帧序号（从0开始），"
        "frame_indices 为属于该穿搭的所有帧序号列表。"
    )
    actual_prompt = prompt.strip() if prompt.strip() else default_prompt

    raw = await call_gemini_api_with_images(
        model_name=model,
        prompt=actual_prompt,
        image_urls=frame_urls,
        temperature=temperature,
        response_schema=_OUTFIT_SELECT_SCHEMA,
    )

    import json as _json
    try:
        data = _json.loads(raw)
        outfits = data.get("outfits", [])
    except Exception as exc:
        raise ValueError(f"穿搭识别 Gemini 返回非 JSON: {raw[:300]}") from exc

    if not outfits:
        raise ValueError("Gemini 未识别出任何穿搭")

    outfit_shots = []
    for outfit in outfits:
        rep_idx = outfit.get("representative_frame_index", 0)
        group_indices = outfit.get("frame_indices", [rep_idx])
        # 找到对应帧
        if 0 <= rep_idx < len(frame_shots):
            shot = frame_shots[rep_idx]
        else:
            shot = frame_shots[0]
        outfit_shots.append({
            "image_url": shot["image_url"],
            "frame_index": shot["frame_index"],
            "group_frame_indices": group_indices,
        })

    logger.info("[%s] Outfit selecting done: %d unique outfits", template_id, len(outfit_shots))
    return outfit_shots


async def _run_outfit_detail_analysis(
    *,
    template_id: str,
    outfit_shots: list[dict],
    model: str,
    prompt: str,
    temperature: float,
) -> list[dict]:
    """
    步骤4a：对每个穿搭图用 Gemini 分析，返回 outfit_details 列表。
    每项：{image_url, frame_index, group_frame_indices, outfit_style, solo_products:[{name,description}]}
    """
    from app.services.ai_api import call_gemini_api_with_images
    import json as _json

    default_prompt = (
        "请分析这张穿搭图，输出整体造型风格描述和图中所有穿搭单品的名称及描述。"
        "以JSON格式返回，outfit_style为整体风格，solo_products为单品数组，每项含name和description。"
    )
    actual_prompt = prompt.strip() if prompt.strip() else default_prompt

    result = []
    for i, outfit in enumerate(outfit_shots):
        outfit_image_url = outfit["image_url"]
        logger.info("[%s] Outfit detail analysis [%d/%d]", template_id, i + 1, len(outfit_shots))
        last_exc = None
        for attempt in range(1, 4):
            try:
                raw = await call_gemini_api_with_images(
                    model_name=model,
                    prompt=actual_prompt,
                    image_urls=[outfit_image_url],
                    temperature=temperature,
                    response_schema=_OUTFIT_DETAIL_SCHEMA,
                )
                detail = _json.loads(raw)
                last_exc = None
                break
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                last_exc = exc
                logger.warning("[%s] Outfit detail [%d] attempt %d/3 failed: %s", template_id, i, attempt, exc)
                if attempt < 3:
                    await asyncio.sleep(min(attempt * 2, 10))
        if last_exc is not None:
            raise ValueError(f"Outfit detail analysis outfit[{i}] failed: {last_exc}") from last_exc

        outfit_style = detail.get("outfit_style", "")
        solo_products = detail.get("solo_products", [])
        logger.info("[%s] Outfit [%d]: style=%s, products=%d", template_id, i, outfit_style[:80], len(solo_products))
        result.append({
            "image_url": outfit_image_url,
            "frame_index": outfit.get("frame_index"),
            "group_frame_indices": outfit.get("group_frame_indices", []),
            "outfit_style": outfit_style,
            "solo_products": solo_products,
        })
    return result


async def _run_product_imagegen(
    *,
    template_id: str,
    outfit_details: list[dict],
    outfit_shots: list[dict],
    model: str,
    prompt: str,
    size: str,
    quality: str,
) -> list[dict]:
    """
    步骤4b：对每个穿搭的每个单品并发生成单品图。
    返回与 outfit_details 同构的列表，solo_products 中加入 product_image_url 字段。
    """
    from app.services.ai_api import generate_image
    from app.services.upload_service import UpstreamImageUploadService, detect_image_content_type

    upload_svc = UpstreamImageUploadService()
    default_prompt = "根据这张穿搭参考图，生成图中【{name}】单品的独立展示图。描述：{description}。保持原图风格，白色或简洁背景，突出单品细节。"

    result = []
    for i, detail in enumerate(outfit_details):
        outfit_image_url = detail["image_url"]
        solo_products = detail.get("solo_products", [])

        async def _gen_one(product: dict, outfit_url: str, idx: int) -> str | None:
            name = product.get("name", "")
            desc = product.get("description", "")
            p_prompt = prompt.strip()
            if not p_prompt:
                p_prompt = default_prompt.format(name=name, description=desc)
            else:
                p_prompt = p_prompt.replace("{name}", name).replace("{description}", desc)
            try:
                img_bytes = await generate_image(
                    model_name=model,
                    prompt=p_prompt,
                    image_urls=[outfit_url],
                    aspect_ratio=size,
                    image_size=quality,
                )
                _ct, _ext = detect_image_content_type(img_bytes)
                res = await upload_svc.upload_image(img_bytes, _ct, f"product_{idx}_{name[:20]}{_ext}")
                return res.url
            except Exception as exc:
                logger.warning("[%s] Product image gen failed outfit[%d] '%s': %s", template_id, i, name, exc)
                return None

        tasks = [_gen_one(p, outfit_image_url, i) for p in solo_products]
        img_urls = await asyncio.gather(*tasks)

        products_with_images = [
            {**p, "product_image_url": url or ""}
            for p, url in zip(solo_products, img_urls)
        ]
        result.append({**detail, "solo_products": products_with_images})
        logger.info("[%s] Product imagegen outfit[%d]: %d products done", template_id, i, len(solo_products))
    return result


def _build_product_search_query(product: dict) -> str:
    """用单品描述组成商品搜索关键词。"""
    return str(product.get("description") or "").strip()


def _with_product_search_skip(product: dict, status: str, *, error: str = "") -> dict:
    generated_image_url = product.get("generated_product_image_url") or product.get("product_image_url") or ""
    updated = {
        **product,
        "generated_product_image_url": generated_image_url,
        "product_search_status": status,
    }
    if error:
        updated["product_search_error"] = error
    return updated


def _truncate_for_log(value: object, max_length: int = 500) -> str:
    text = str(value or "").replace("\n", " ").strip()
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}..."


async def _search_product_top_match(
    *,
    client: httpx.AsyncClient,
    template_id: str,
    product: dict,
    outfit_index: int,
    product_index: int,
) -> dict:
    """
    用生成的单品图 + 单品描述搜索真实商品。
    命中 topMatch 时，用真实商品 image/thumbnail 替换 product_image_url。
    """
    generated_image_url = str(
        product.get("generated_product_image_url") or product.get("product_image_url") or ""
    ).strip()
    if not generated_image_url:
        return _with_product_search_skip(product, "skipped_no_image")

    api_url = settings.product_search_api_url.strip()
    if not api_url:
        return _with_product_search_skip(product, "skipped_no_api_url")

    query = _build_product_search_query(product)
    top_n = min(max(int(settings.product_search_top_n or 3), 1), 10)
    internal_score_threshold = min(max(float(settings.product_search_internal_score_threshold), 0.0), 1.0)
    payload: dict[str, object] = {
        "imageUrl": generated_image_url,
        "internalScoreThreshold": internal_score_threshold,
        "topN": top_n,
    }
    if query:
        payload["q"] = query

    name = product.get("name") or f"product[{product_index}]"
    try:
        resp = await client.post(api_url, json=payload)
        response_text = resp.text
        if resp.status_code >= 400:
            error = f"HTTP {resp.status_code}: {_truncate_for_log(response_text)}"
            logger.warning(
                "[%s] Product search HTTP failed outfit[%d] '%s': status=%d query=%r image_url=%s response=%s",
                template_id,
                outfit_index,
                name,
                resp.status_code,
                query,
                _truncate_for_log(generated_image_url, 180),
                _truncate_for_log(response_text),
            )
            return {
                **_with_product_search_skip(product, "failed", error=error),
                "product_search_http_status": resp.status_code,
                "product_search_response": _truncate_for_log(response_text, 1000),
            }

        try:
            body = resp.json()
        except Exception as exc:
            error = f"Invalid JSON response: {_truncate_for_log(response_text)}"
            logger.warning(
                "[%s] Product search invalid JSON outfit[%d] '%s': query=%r image_url=%s response=%s",
                template_id,
                outfit_index,
                name,
                query,
                _truncate_for_log(generated_image_url, 180),
                _truncate_for_log(response_text),
            )
            return _with_product_search_skip(product, "failed", error=error)

        if not isinstance(body, dict):
            raise ValueError("search response is not an object")
        if body.get("code") != 0 or body.get("success") is False:
            error = body.get("message") or f"search response code={body.get('code')}"
            logger.warning(
                "[%s] Product search API failed outfit[%d] '%s': code=%s success=%s trace_id=%s query=%r message=%s",
                template_id,
                outfit_index,
                name,
                body.get("code"),
                body.get("success"),
                body.get("traceId") or "",
                query,
                error,
            )
            return {
                **_with_product_search_skip(product, "failed", error=str(error)),
                "product_search_trace_id": body.get("traceId") or "",
                "product_search_response_code": body.get("code"),
                "product_search_response_message": body.get("message") or "",
            }

        data = body.get("data") or {}
        if not isinstance(data, dict):
            raise ValueError("search response data is not an object")
        top_match = data.get("topMatch")
        candidates = data.get("candidates") or []
        if not isinstance(top_match, dict) or not top_match:
            logger.info("[%s] Product search no match outfit[%d] '%s'", template_id, outfit_index, name)
            return {
                **product,
                "generated_product_image_url": generated_image_url,
                "product_search_status": "no_match",
                "product_search_query": query,
                "product_search_trace_id": body.get("traceId") or "",
                "product_search_candidates": candidates,
            }

        matched_image_url = top_match.get("image") or top_match.get("thumbnail") or generated_image_url
        logger.info(
            "[%s] Product search matched outfit[%d] '%s': %s",
            template_id,
            outfit_index,
            name,
            str(top_match.get("title") or "")[:100],
        )
        return {
            **product,
            "generated_product_image_url": generated_image_url,
            "product_image_url": matched_image_url,
            "product_search_status": "matched",
            "product_search_query": query,
            "product_search_trace_id": body.get("traceId") or "",
            "product_search_processing_time": data.get("processingTime") or "",
            "product_search_candidates": candidates,
            "matched_product": top_match,
            "product_title": top_match.get("title") or product.get("name") or "",
            "product_link": top_match.get("link") or "",
            "product_source": top_match.get("source") or "",
            "product_thumbnail": top_match.get("thumbnail") or "",
            "product_price": top_match.get("price"),
            "product_tier": top_match.get("tier"),
            "product_tier_label": top_match.get("tier_label") or "",
        }
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning("[%s] Product search failed outfit[%d] '%s': %s", template_id, outfit_index, name, exc)
        return _with_product_search_skip(product, "failed", error=str(exc))


async def _run_product_search(
    *,
    template_id: str,
    product_gen_results: list[dict],
) -> list[dict]:
    """
    步骤4b2：单品图生成后搜索真实商品，topMatch 作为结果商品。
    返回结构与 product_gen_results 同构，但 solo_products 会带 matched_product，
    且 product_image_url 替换为真实商品图。
    """
    if not product_gen_results:
        return []

    timeout_seconds = max(float(settings.product_search_timeout_seconds or 45.0), 1.0)
    result = [
        {**detail, "solo_products": list(detail.get("solo_products") or [])}
        for detail in product_gen_results
    ]
    jobs: list[tuple[int, int, dict]] = []
    for outfit_index, detail in enumerate(result):
        for product_index, product in enumerate(detail.get("solo_products") or []):
            jobs.append((outfit_index, product_index, product))

    if not jobs:
        return result

    semaphore = asyncio.Semaphore(_PRODUCT_SEARCH_CONCURRENCY)
    timeout = httpx.Timeout(timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        async def _run_one(outfit_index: int, product_index: int, product: dict) -> tuple[int, int, dict]:
            async with semaphore:
                searched = await _search_product_top_match(
                    client=client,
                    template_id=template_id,
                    product=product,
                    outfit_index=outfit_index,
                    product_index=product_index,
                )
                return outfit_index, product_index, searched

        updates = await asyncio.gather(
            *[_run_one(outfit_index, product_index, product) for outfit_index, product_index, product in jobs]
        )

    matched_count = 0
    for outfit_index, product_index, product in updates:
        result[outfit_index]["solo_products"][product_index] = product
        if product.get("product_search_status") == "matched":
            matched_count += 1

    logger.info("[%s] Product search stage completed: %d/%d matched", template_id, matched_count, len(jobs))
    return result


def _get_outfit_regen_product_image_url(product: dict) -> tuple[str, str]:
    """返回 (外部商品图URL, AI生成单品图URL)。外部图优先，不可用时降级到AI图。"""
    external_url = ""
    matched_product = product.get("matched_product")
    if isinstance(matched_product, dict):
        image_url = matched_product.get("image") or matched_product.get("thumbnail")
        if image_url:
            external_url = str(image_url)
    # generated_product_image_url 是 AI 生成的 CDN 图（始终可访问）
    # product_image_url 在搜索命中后会被覆写为外部商品图，不能作为 AI fallback
    ai_url = str(product.get("generated_product_image_url") or "")
    return external_url, ai_url


async def _resolve_product_image_url(ext_url: str, ai_url: str) -> str:
    """优先使用外部商品图；若 HEAD 请求返回 4xx，降级到 AI 生成的 CDN 图。"""
    if not ext_url:
        return ai_url
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.head(ext_url)
            if resp.status_code < 400:
                return ext_url
            logger.warning("外部商品图不可访问 status=%d url=%s，降级到AI图", resp.status_code, ext_url[:120])
    except Exception as exc:
        logger.warning("外部商品图 HEAD 检查失败: %s url=%s，降级到AI图", exc, ext_url[:120])
    return ai_url


async def _run_outfit_regen(
    *,
    template_id: str,
    outfit_details: list[dict],
    product_gen_results: list[dict],
    outfit_shots: list[dict],
    model: str,
    prompt: str,
    size: str,
    quality: str,
) -> list[dict]:
    """
    步骤4c：对每个穿搭，用所有单品图 + outfit_style 生成新造型图。
    返回最终 final_outfits 列表，image_url 为新造型图 URL。
    """
    from app.services.ai_api import generate_image
    from app.services.upload_service import UpstreamImageUploadService, detect_image_content_type

    upload_svc = UpstreamImageUploadService()
    default_prompt = "根据以下单品图片，生成一张完整穿搭造型图。整体风格：{outfit_style}。人物使用商场展示用的塑料模特形象（非真人），面部为光滑无表情的标准模特脸，保持服装风格一致，背景简洁时尚。"

    final_outfits = []
    for i, detail in enumerate(product_gen_results):
        outfit_image_url = detail["image_url"]
        outfit_style = detail.get("outfit_style", "")
        solo_products = detail.get("solo_products", [])
        product_cdn_urls = []
        for p in solo_products:
            ext_url, ai_url = _get_outfit_regen_product_image_url(p)
            url = await _resolve_product_image_url(ext_url, ai_url)
            if url:
                product_cdn_urls.append(url)

        new_outfit_url = outfit_image_url
        # 没有单品图时，用 outfit 原截图作为唯一参考图
        ref_urls = product_cdn_urls if product_cdn_urls else ([outfit_image_url] if outfit_image_url else [])
        if not product_cdn_urls:
            logger.info(
                "[%s] Outfit regen [%d] no product images (solo_products=%d), using outfit shot as ref",
                template_id, i, len(solo_products),
            )
        if ref_urls:
            r_prompt = prompt.strip()
            if not r_prompt:
                r_prompt = default_prompt.format(outfit_style=outfit_style)
            else:
                r_prompt = r_prompt.replace("{outfit_style}", outfit_style)
            try:
                img_bytes = await generate_image(
                    model_name=model,
                    prompt=r_prompt,
                    image_urls=ref_urls,
                    aspect_ratio=size,
                    image_size=quality,
                )
                _ct, _ext = detect_image_content_type(img_bytes)
                res = await upload_svc.upload_image(img_bytes, _ct, f"outfit_regen_{i}{_ext}")
                new_outfit_url = res.url
                logger.info("[%s] Outfit regen [%d] uploaded: %s", template_id, i, new_outfit_url[:80])
            except Exception as exc:
                logger.warning("[%s] Outfit regen [%d] failed, using original: %s", template_id, i, exc)

        final_outfits.append({
            **detail,
            "image_url": new_outfit_url,
            "original_outfit_image_url": outfit_image_url,
        })
    return final_outfits


# =============================================================================
# 处理管道（Pipeline）
# =============================================================================


async def _sync_task_shots(
    template_id: str,
    uuid_val: UUID,
    final_outfits: list[dict],
    prompt_description: str | None = None,
) -> None:
    """
    将重新分析后的 prompt 和 final_outfits 同步回关联该模板的所有 video_tasks。
    - has_face=True：shots[0] 是人脸图，保留不动，从 shots[1:] 开始替换为造型图
    - has_face=False：整个 shots 替换为造型图
    """
    from sqlalchemy import select as sa_select
    from app.models.video_task import VideoTask

    outfit_shots = [
        enrich_shot_with_ext_products({
            "image_url": o["image_url"],
            "outfit_style": o.get("outfit_style", ""),
            "solo_products": o.get("solo_products", []),
        })
        for o in final_outfits
        if o.get("image_url")
    ]
    prompt_text = (prompt_description or "").strip()
    if not outfit_shots and not prompt_text:
        return

    async with SessionLocal() as session:
        tasks = (await session.execute(
            sa_select(VideoTask).where(VideoTask.template_id == uuid_val)
        )).scalars().all()

        for task in tasks:
            if outfit_shots:
                existing = list(task.shots or [])
                if task.has_face and existing:
                    # 保留首位人脸图，其余替换为造型图
                    task.shots = [existing[0], *outfit_shots]
                else:
                    task.shots = outfit_shots
            if prompt_text:
                task.prompt = prompt_text
                task.is_prompt_updated = True

        await session.commit()

    logger.info(
        "[%s] synced prompt/shots to %d tasks (%d outfits, prompt=%s chars)",
        template_id,
        len(tasks),
        len(outfit_shots),
        len(prompt_description or ""),
    )


async def _delete_template_and_video_source(template_id: str, uuid_val: UUID) -> None:
    """删除模板及其关联的视频源（用于阶段3/4不可恢复失败时的清理）。"""
    try:
        async with SessionLocal() as session:
            tpl = await session.get(VideoAITemplate, uuid_val)
            if tpl:
                video_source_id = tpl.video_source_id
                await session.delete(tpl)
                await session.flush()
                if video_source_id:
                    from app.models.video_source import VideoSource
                    vs = await session.get(VideoSource, video_source_id)
                    if vs:
                        await session.delete(vs)
                await session.commit()
                logger.info("[%s] template and video source deleted after unrecoverable failure", template_id)
    except Exception as exc:
        logger.error("[%s] failed to delete template/video source: %s", template_id, exc)


async def _run_pipeline(template_id: str, semaphore: asyncio.Semaphore) -> None:
    """
    执行视频 AI 处理管道

    流程（按顺序）：
        imagegen → outfit_selecting → outfit_detailing →
        intent_classify → understanding →
        product_imagegen → product_search → outfit_regen

    Args:
        template_id: 模板 ID
        semaphore: 并发控制信号量
    """
    async with semaphore:
        try:
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

                # 加载用户流程配置
                from app.services.pipeline_settings_service import get_or_create_pipeline_settings
                if tpl.owner_id is not None:
                    pipeline_cfg = await get_or_create_pipeline_settings(session, owner_id=tpl.owner_id)
                    # 视频理解（在 outfit_detailing 之后，按 content_intent 分支）
                    understand_model = pipeline_cfg.understand_model or "gemini-3.1-pro-preview"
                    understand_temperature = pipeline_cfg.understand_temperature
                    understand_prompts_by_intent = {
                        "beauty_show": pipeline_cfg.understand_prompt_beauty_show or "",
                        "knowledge": pipeline_cfg.understand_prompt_knowledge or "",
                        "persona_story": pipeline_cfg.understand_prompt_persona_story or "",
                        "trend_meme": pipeline_cfg.understand_prompt_trend_meme or "",
                    }
                    # 意图识别
                    intent_classify_model = pipeline_cfg.intent_classify_model or "gemini-3.1-pro-preview"
                    intent_classify_prompt = pipeline_cfg.intent_classify_prompt or ""
                    intent_classify_temperature = pipeline_cfg.intent_classify_temperature
                    # 穿搭识别
                    outfit_select_model = pipeline_cfg.outfit_select_model or "gemini-3.1-pro-preview"
                    outfit_select_prompt = pipeline_cfg.outfit_select_prompt or ""
                    outfit_select_temperature = pipeline_cfg.outfit_select_temperature
                    # 穿搭单品理解
                    outfit_detail_model = pipeline_cfg.outfit_detail_model or "gemini-3.1-pro-preview"
                    outfit_detail_prompt = pipeline_cfg.outfit_detail_prompt or ""
                    outfit_detail_temperature = pipeline_cfg.outfit_detail_temperature
                    # 单品图生成
                    product_imagegen_model = pipeline_cfg.product_imagegen_model or "gemini-3.1-flash-image-preview"
                    product_imagegen_prompt = pipeline_cfg.product_imagegen_prompt or ""
                    product_imagegen_size = pipeline_cfg.product_imagegen_size or "1:1"
                    product_imagegen_quality = pipeline_cfg.product_imagegen_quality or "2K"
                    # 新造型图生成
                    outfit_regen_model = pipeline_cfg.outfit_regen_model or "gemini-3.1-flash-image-preview"
                    outfit_regen_prompt = pipeline_cfg.outfit_regen_prompt or ""
                    outfit_regen_size = pipeline_cfg.outfit_regen_size or "9:16"
                    outfit_regen_quality = pipeline_cfg.outfit_regen_quality or "2K"
                else:
                    understand_model = "gemini-3.1-pro-preview"
                    understand_temperature = 0.3
                    understand_prompts_by_intent = {k: "" for k in ALLOWED_INTENTS}
                    intent_classify_model = "gemini-3.1-pro-preview"
                    intent_classify_prompt = ""
                    intent_classify_temperature = 0.3
                    outfit_select_model = "gemini-3.1-pro-preview"
                    outfit_select_prompt = ""
                    outfit_select_temperature = 0.3
                    outfit_detail_model = "gemini-3.1-pro-preview"
                    outfit_detail_prompt = ""
                    outfit_detail_temperature = 0.3
                    product_imagegen_model = "gemini-3.1-flash-image-preview"
                    product_imagegen_prompt = ""
                    product_imagegen_size = "1:1"
                    product_imagegen_quality = "2K"
                    outfit_regen_model = "gemini-3.1-flash-image-preview"
                    outfit_regen_prompt = ""
                    outfit_regen_size = "9:16"
                    outfit_regen_quality = "2K"
            # 获取当前 state（可能带有已完成阶段信息）
            state = video_ai_states.setdefault(template_id, _new_state(template_id, VideoAIProcessStatus.pending))
            state["completed_stages"] = list(state.get("completed_stages") or [])
            completed_stages: list[str] = state["completed_stages"]

            # 断点续跑：从 DB extra 字段恢复中间阶段数据（内存 state 可能已清空）
            async with SessionLocal() as session:
                _tpl_for_restore = await session.get(VideoAITemplate, uuid_val)
                _extra = dict(_tpl_for_restore.extra or {}) if _tpl_for_restore else {}
            if (
                "product_imagegen" in completed_stages
                and _PRODUCT_SEARCH_STAGE not in completed_stages
                and "outfit_regen" in completed_stages
            ):
                _remove_completed_stage(state, "outfit_regen")
                completed_stages = state["completed_stages"]
                state["final_outfits"] = []
                state["extracted_shots"] = []
                _mark_dirty(template_id)
                async with SessionLocal() as session:
                    tpl = await session.get(VideoAITemplate, uuid_val)
                    if tpl:
                        extra = dict(tpl.extra or {})
                        extra.pop("final_outfits", None)
                        tpl.extra = extra
                        tpl.extracted_shots = []
                        tpl.process_state = json.dumps(state, ensure_ascii=False)
                        await session.commit()
                logger.info("[%s] product_search missing; outfit_regen will rerun after product search", template_id)
            if "imagegen" in completed_stages and not state.get("frame_shots"):
                state["frame_shots"] = _extra.get("frame_shots") or []
            if "outfit_selecting" in completed_stages and not state.get("outfit_shots"):
                state["outfit_shots"] = _extra.get("outfit_shots") or []
            if "outfit_regen" in completed_stages and not state.get("final_outfits"):
                state["final_outfits"] = _extra.get("final_outfits") or []
            if "outfit_detailing" in completed_stages and not state.get("outfit_detailing_progress"):
                state["outfit_detailing_progress"] = _extra.get("outfit_detailing_progress") or []
            if "intent_classify" in completed_stages and not state.get("intent_json"):
                state["intent_json"] = _extra.get("intent_json") or {}
            if ("product_imagegen" in completed_stages or _PRODUCT_SEARCH_STAGE in completed_stages) and not state.get("product_gen_results"):
                state["product_gen_results"] = _extra.get("product_search_results") or _extra.get("product_gen_results") or []
            if _PRODUCT_SEARCH_STAGE in completed_stages and not state.get("product_search_results"):
                state["product_search_results"] = _extra.get("product_search_results") or state.get("product_gen_results") or []

            # ========== 步骤 1: 抽帧并上传 CDN（1s一帧，最多重试 3 次）==========
            # 流水线顺序：
            # 1) imagegen → 2) outfit_selecting → 3) outfit_detailing
            # 4) intent_classify → 5) understanding
            # 6) product_imagegen → 7) product_search → 8) outfit_regen
            # （视频理解依赖 outfit_detailing 输出的 solo_products 与 intent_classify 输出的 JSON）
            if "imagegen" in completed_stages:
                frame_shots = state.get("frame_shots") or []
                logger.info("[%s] imagegen(frame extraction) skipped (already completed), %d frames", template_id, len(frame_shots))
            else:
                _set_status(template_id, VideoAIProcessStatus.imagegen)
                logger.info("[%s] imagegen(frame extraction) stage started", template_id)

                last_exc = None
                for attempt in range(1, 4):
                    try:
                        frame_shots = await _run_imagegen_stage(
                            template_id=template_id,
                            video_url=video_url,
                        )
                        last_exc = None
                        break
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        last_exc = exc
                        delay = min(attempt * 2, 30)
                        logger.warning("[%s] imagegen attempt %d/3 failed (%ds后重试): %s", template_id, attempt, delay, exc)
                        if attempt < 3:
                            await asyncio.sleep(delay)
                if last_exc is not None:
                    raise last_exc

                state = video_ai_states.setdefault(template_id, _new_state(template_id, VideoAIProcessStatus.imagegen))
                state["frame_shots"] = frame_shots
                state["updated_at"] = _utcnow_iso()
                if "imagegen" not in state.get("completed_stages", []):
                    state.setdefault("completed_stages", []).append("imagegen")
                _mark_dirty(template_id)

                # 快照帧图到 extra.frame_shots
                async with SessionLocal() as session:
                    tpl = await session.get(VideoAITemplate, uuid_val)
                    if tpl:
                        extra = dict(tpl.extra or {})
                        extra["frame_shots"] = frame_shots
                        tpl.extra = extra
                        tpl.process_state = json.dumps(state, ensure_ascii=False)
                        await session.commit()
                logger.info("[%s] imagegen stage completed, %d frames saved", template_id, len(frame_shots))

            # ========== 步骤 2: Gemini 识别 Unique 穿搭（最多重试 3 次）==========
            if "outfit_selecting" in completed_stages:
                outfit_shots = state.get("outfit_shots") or []
                logger.info("[%s] outfit_selecting skipped (already completed), %d outfits", template_id, len(outfit_shots))
            else:
                _set_status(template_id, VideoAIProcessStatus.outfit_selecting)
                logger.info("[%s] outfit_selecting stage started, %d frames", template_id, len(frame_shots))

                last_exc = None
                for attempt in range(1, 4):
                    try:
                        outfit_shots = await _run_outfit_selecting_stage(
                            template_id=template_id,
                            frame_shots=frame_shots,
                            model=outfit_select_model,
                            prompt=outfit_select_prompt,
                            temperature=outfit_select_temperature,
                        )
                        last_exc = None
                        break
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        last_exc = exc
                        delay = min(attempt * 2, 30)
                        logger.warning("[%s] outfit_selecting attempt %d/3 failed: %s", template_id, attempt, exc)
                        if attempt < 3:
                            await asyncio.sleep(delay)
                if last_exc is not None:
                    raise last_exc

                state = video_ai_states.setdefault(template_id, _new_state(template_id, VideoAIProcessStatus.outfit_selecting))
                state["outfit_shots"] = outfit_shots
                state["updated_at"] = _utcnow_iso()
                if "outfit_selecting" not in state.get("completed_stages", []):
                    state.setdefault("completed_stages", []).append("outfit_selecting")
                _mark_dirty(template_id)

                async with SessionLocal() as session:
                    tpl = await session.get(VideoAITemplate, uuid_val)
                    if tpl:
                        extra = dict(tpl.extra or {})
                        extra["outfit_shots"] = outfit_shots
                        tpl.extra = extra
                        tpl.process_state = json.dumps(state, ensure_ascii=False)
                        await session.commit()
                logger.info("[%s] outfit_selecting stage completed, %d unique outfits", template_id, len(outfit_shots))

            # ========== 步骤 3: 穿搭单品理解（每个穿搭 → outfit_style + solo_products）==========
            if "outfit_detailing" in completed_stages:
                outfit_details = state.get("outfit_detailing_progress") or []
                logger.info("[%s] outfit_detailing skipped (already completed), %d outfits", template_id, len(outfit_details))
            else:
                _set_status(template_id, VideoAIProcessStatus.outfit_detailing)
                logger.info("[%s] outfit_detailing stage started, %d outfits", template_id, len(outfit_shots))
                outfit_details = await _run_outfit_detail_analysis(
                    template_id=template_id,
                    outfit_shots=outfit_shots,
                    model=outfit_detail_model,
                    prompt=outfit_detail_prompt,
                    temperature=outfit_detail_temperature,
                )
                state["outfit_detailing_progress"] = outfit_details
                state["updated_at"] = _utcnow_iso()
                if "outfit_detailing" not in state.get("completed_stages", []):
                    state.setdefault("completed_stages", []).append("outfit_detailing")
                _mark_dirty(template_id)
                async with SessionLocal() as session:
                    tpl = await session.get(VideoAITemplate, uuid_val)
                    if tpl:
                        extra = dict(tpl.extra or {})
                        extra["outfit_detailing_progress"] = outfit_details
                        tpl.extra = extra
                        tpl.process_state = json.dumps(state, ensure_ascii=False)
                        await session.commit()
                logger.info("[%s] outfit_detailing stage completed, %d outfits analyzed", template_id, len(outfit_details))

            # ========== 步骤 4: 意图识别（JSON 输出，最多重试 3 次）==========
            if "intent_classify" in completed_stages:
                intent_json = state.get("intent_json") or {}
                logger.info("[%s] intent_classify skipped (already completed), intent=%s",
                            template_id, intent_json.get("content_intent"))
            else:
                _set_status(template_id, VideoAIProcessStatus.understanding)
                logger.info("[%s] intent_classify stage started", template_id)
                intent_json = await _run_intent_classify_stage(
                    template_id=template_id,
                    video_url=video_url,
                    outfit_details=outfit_details,
                    model=intent_classify_model,
                    prompt=intent_classify_prompt,
                    temperature=intent_classify_temperature,
                )
                state["intent_json"] = intent_json
                state["updated_at"] = _utcnow_iso()
                if "intent_classify" not in state.get("completed_stages", []):
                    state.setdefault("completed_stages", []).append("intent_classify")
                _mark_dirty(template_id)
                async with SessionLocal() as session:
                    tpl = await session.get(VideoAITemplate, uuid_val)
                    if tpl:
                        extra = dict(tpl.extra or {})
                        extra["intent_json"] = intent_json
                        tpl.extra = extra
                        tpl.process_state = json.dumps(state, ensure_ascii=False)
                        await session.commit()
                logger.info("[%s] intent_classify stage completed", template_id)

            # ========== 步骤 5: 视频理解（按 content_intent 选 prompt，输出文本）==========
            if "understanding" in completed_stages:
                prompt_description = state.get("prompt_description") or ""
                logger.info("[%s] understanding skipped (already completed), prompt_description=%d chars",
                            template_id, len(prompt_description))
            else:
                _set_status(template_id, VideoAIProcessStatus.understanding)
                logger.info("[%s] understanding stage started", template_id)
                prompt_description = await _run_understanding_stage(
                    template_id=template_id,
                    video_url=video_url,
                    intent_json=intent_json,
                    model=understand_model,
                    temperature=understand_temperature,
                    prompts_by_intent=understand_prompts_by_intent,
                )
                state["prompt_description"] = prompt_description
                state["updated_at"] = _utcnow_iso()
                if "understanding" not in state.get("completed_stages", []):
                    state.setdefault("completed_stages", []).append("understanding")
                _mark_dirty(template_id)
                async with SessionLocal() as session:
                    tpl = await session.get(VideoAITemplate, uuid_val)
                    if tpl:
                        tpl.prompt_description = prompt_description
                        tpl.process_state = json.dumps(state, ensure_ascii=False)
                        await session.commit()
                logger.info("[%s] understanding stage completed", template_id)

            # ========== 步骤 6: 单品图生成 ==========
            if "product_imagegen" in completed_stages:
                product_gen_results = state.get("product_gen_results") or []
                logger.info("[%s] product_imagegen skipped (already completed)", template_id)
            else:
                _set_status(template_id, VideoAIProcessStatus.product_imagegen)
                logger.info("[%s] product_imagegen stage started", template_id)
                product_gen_results = await _run_product_imagegen(
                    template_id=template_id,
                    outfit_details=outfit_details,
                    outfit_shots=outfit_shots,
                    model=product_imagegen_model,
                    prompt=product_imagegen_prompt,
                    size=product_imagegen_size,
                    quality=product_imagegen_quality,
                )
                state["product_gen_results"] = product_gen_results
                state["updated_at"] = _utcnow_iso()
                if "product_imagegen" not in state.get("completed_stages", []):
                    state.setdefault("completed_stages", []).append("product_imagegen")
                _mark_dirty(template_id)
                async with SessionLocal() as session:
                    tpl = await session.get(VideoAITemplate, uuid_val)
                    if tpl:
                        extra = dict(tpl.extra or {})
                        extra["product_gen_results"] = product_gen_results
                        tpl.extra = extra
                        tpl.process_state = json.dumps(state, ensure_ascii=False)
                        await session.commit()
                logger.info("[%s] product_imagegen stage completed", template_id)

            # ========== 步骤 7: 商品搜索（单品描述 + 单品图 → topMatch）==========
            if _PRODUCT_SEARCH_STAGE in completed_stages:
                product_gen_results = state.get("product_search_results") or state.get("product_gen_results") or []
                logger.info("[%s] product_search skipped (already completed)", template_id)
            else:
                _set_status(template_id, VideoAIProcessStatus.product_imagegen)
                logger.info("[%s] product_search stage started", template_id)
                product_gen_results = await _run_product_search(
                    template_id=template_id,
                    product_gen_results=product_gen_results,
                )
                state["product_gen_results"] = product_gen_results
                state["product_search_results"] = product_gen_results
                state["updated_at"] = _utcnow_iso()
                if _PRODUCT_SEARCH_STAGE not in state.get("completed_stages", []):
                    state.setdefault("completed_stages", []).append(_PRODUCT_SEARCH_STAGE)
                _mark_dirty(template_id)
                async with SessionLocal() as session:
                    tpl = await session.get(VideoAITemplate, uuid_val)
                    if tpl:
                        extra = dict(tpl.extra or {})
                        extra["product_gen_results"] = product_gen_results
                        extra["product_search_results"] = product_gen_results
                        tpl.extra = extra
                        tpl.process_state = json.dumps(state, ensure_ascii=False)
                        await session.commit()
                logger.info("[%s] product_search stage completed", template_id)

            # ========== 步骤 8: 新造型图生成 ==========
            if "outfit_regen" in completed_stages:
                final_outfits = state.get("final_outfits") or []
                logger.info("[%s] outfit_regen skipped (already completed), %d outfits", template_id, len(final_outfits))
            else:
                _set_status(template_id, VideoAIProcessStatus.outfit_regen)
                logger.info("[%s] outfit_regen stage started", template_id)
                final_outfits = await _run_outfit_regen(
                    template_id=template_id,
                    outfit_details=outfit_details,
                    product_gen_results=product_gen_results,
                    outfit_shots=outfit_shots,
                    model=outfit_regen_model,
                    prompt=outfit_regen_prompt,
                    size=outfit_regen_size,
                    quality=outfit_regen_quality,
                )
                extracted_shots_final = [
                    enrich_shot_with_ext_products({
                        "image_url": o["image_url"],
                        "outfit_style": o.get("outfit_style", ""),
                        "solo_products": o.get("solo_products", []),
                    })
                    for o in final_outfits
                ]
                state["final_outfits"] = final_outfits
                state["extracted_shots"] = extracted_shots_final
                state["updated_at"] = _utcnow_iso()
                if "outfit_regen" not in state.get("completed_stages", []):
                    state.setdefault("completed_stages", []).append("outfit_regen")
                _mark_dirty(template_id)
                async with SessionLocal() as session:
                    tpl = await session.get(VideoAITemplate, uuid_val)
                    if tpl:
                        tpl.extracted_shots = extracted_shots_final
                        extra = dict(tpl.extra or {})
                        extra["final_outfits"] = final_outfits
                        tpl.extra = extra
                        tpl.process_state = json.dumps(state, ensure_ascii=False)
                        await session.commit()
                logger.info("[%s] outfit_regen stage completed, %d outfits saved", template_id, len(final_outfits))

            # ========== 步骤 N: 成功 ==========
            _set_status(template_id, VideoAIProcessStatus.success)
            logger.info("[%s] pipeline completed", template_id)

            # 最终持久化
            await _persist_states([template_id])

            # 如果是"一键重新分析"触发的，同步 shots 到关联 video_tasks
            if template_id in _sync_shots_on_success:
                _sync_shots_on_success.discard(template_id)
                _final_outfits = state.get("final_outfits") or []
                await _sync_task_shots(
                    template_id,
                    uuid_val,
                    _final_outfits,
                    state.get("prompt_description") or "",
                )

        except asyncio.CancelledError:
            # 进程关停时取消的任务保留运行中状态，由 recover_stuck_templates_on_startup 续跑；
            # 仅在用户显式 pause 触发的取消时写 paused。
            if not _shutting_down:
                _set_status(template_id, VideoAIProcessStatus.paused)
                await _persist_states([template_id])
            else:
                logger.info("[%s] pipeline cancelled due to shutdown; status preserved for resume", template_id)
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
            state = video_ai_states.get(template_id)
            if state and state.get("status") == VideoAIProcessStatus.paused.value:
                logger.info("[%s] skip queued template because it is paused in memory", template_id)
                video_ai_queue.task_done()
                continue
            try:
                uuid_val = UUID(template_id)
                async with SessionLocal() as session:
                    tpl = await session.get(VideoAITemplate, uuid_val)
                    if tpl and tpl.process_status == VideoAIProcessStatus.paused:
                        logger.info("[%s] skip queued template because it is paused in DB", template_id)
                        video_ai_queue.task_done()
                        continue
            except ValueError:
                logger.warning("Invalid template id in video AI queue: %s", template_id)
                video_ai_queue.task_done()
                continue
            except Exception as exc:
                logger.warning("[%s] failed to check queued template status, will run anyway: %s", template_id, exc)
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


async def enqueue_template(template_id: str, *, clear_stages: bool = False) -> None:
    """
    将模板加入队列并标记为等待中。

    Args:
        template_id: 模板 ID
        clear_stages: 为 True 时清空 completed_stages，从头重跑；默认 False（断点续跑）
    """
    # 如果内存中没有状态（如服务重启），先从 DB 的 process_state 字段恢复
    if template_id not in video_ai_states:
        try:
            uuid_val = UUID(template_id)
            async with SessionLocal() as session:
                tpl = await session.get(VideoAITemplate, uuid_val)
                if tpl and tpl.process_state:
                    saved = json.loads(tpl.process_state)
                    video_ai_states[template_id] = saved
                    logger.info("[%s] restored state from DB: completed_stages=%s",
                                template_id, saved.get("completed_stages", []))
        except Exception as exc:
            logger.warning("[%s] failed to restore state from DB: %s", template_id, exc)

    # 保留已有 state（保留 completed_stages 和已产出数据）
    state = video_ai_states.setdefault(template_id, _new_state(template_id, VideoAIProcessStatus.pending))
    if clear_stages:
        state["completed_stages"] = []
        state["prompt_description"] = ""
        state["extracted_shots"] = []
        for key in (
            "frame_shots", "outfit_shots", "outfit_detailing_progress",
            "intent_json", "product_gen_results", "product_search_results", "final_outfits",
        ):
            state.pop(key, None)
        # 同步清掉 DB extra 与 extracted_shots，并重置 process_status，避免队列处理器跳过 paused/fail 模板
        try:
            uuid_val = UUID(template_id)
            async with SessionLocal() as session:
                tpl = await session.get(VideoAITemplate, uuid_val)
                if tpl:
                    extra = dict(tpl.extra or {})
                    for key in (
                        "frame_shots", "outfit_shots", "outfit_detailing_progress",
                        "intent_json", "product_gen_results", "product_search_results", "final_outfits",
                    ):
                        extra.pop(key, None)
                    tpl.extra = extra
                    tpl.extracted_shots = []
                    tpl.prompt_description = ""
                    tpl.process_status = VideoAIProcessStatus.pending
                    tpl.process_error = None
                    await session.commit()
        except Exception as exc:
            logger.warning("[%s] enqueue_template clear_stages DB cleanup failed: %s", template_id, exc)
        logger.info("[%s] restarting from scratch (completed_stages cleared)", template_id)
    else:
        logger.info("[%s] resuming from completed_stages=%s", template_id, state.get("completed_stages", []))
    state["status"] = VideoAIProcessStatus.pending.value
    state["error_message"] = ""
    state["updated_at"] = _utcnow_iso()
    _mark_dirty(template_id)

    _ensure_persist_worker()
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
    断点续跑：保留已完成阶段，从失败/暂停处继续。
    """
    await enqueue_template(template_id, clear_stages=False)


async def restart_template(template_id: str) -> None:
    """
    从头重跑：清空已完成阶段，重新执行所有步骤。
    """
    await enqueue_template(template_id, clear_stages=True)


async def restart_from_stage2(template_id: str) -> None:
    """
    重新生图：清除全部已完成阶段与中间产物，从头开始整条流水线。

    新管道下视频理解依赖 outfit_detailing 输出，无法再独立保留，因此与
    `restart_template` 行为一致——保留入口名以兼容现有调用方/前端按钮。
    """
    await enqueue_template(template_id, clear_stages=True)
    logger.info("[%s] restart_from_stage2 (full reset) enqueued", template_id)


async def batch_restart_templates(
    owner_id: str | None = None,
    template_ids: list[str] | None = None,
) -> dict:
    """
    批量全流程重跑：入队 → 等待每个 pipeline 完成 → 同步 shots 到关联 video_tasks。
    传入 template_ids 则只处理这些模板；否则处理该 owner 所有模板。
    """
    from sqlalchemy import select as sa_select
    from uuid import UUID

    async with SessionLocal() as session:
        stmt = sa_select(VideoAITemplate.id)
        if owner_id is not None:
            stmt = stmt.where(VideoAITemplate.owner_id == UUID(owner_id))
        if template_ids is not None:
            stmt = stmt.where(VideoAITemplate.id.in_([UUID(tid) for tid in template_ids]))
        rows = (await session.execute(stmt)).scalars().all()

    tids = [str(tid) for tid in rows]
    if not tids:
        return {"total": 0, "success": 0, "fail": 0}

    logger.info("batch_restart started: %d templates", len(tids))
    success_count = 0
    fail_count = 0
    for tid in tids:
        try:
            _sync_shots_on_success.add(tid)
            await restart_template(tid)
            success_count += 1
        except Exception as exc:
            _sync_shots_on_success.discard(tid)
            fail_count += 1
            logger.error("[%s] batch_restart failed: %s", tid, exc)

    logger.info("batch_restart enqueued: total=%d success=%d fail=%d", len(tids), success_count, fail_count)
    return {"total": len(tids), "success": success_count, "fail": fail_count}


async def batch_retry_templates(
    owner_id: str | None = None,
    template_ids: list[str] | None = None,
) -> dict:
    """
    批量断点续跑失败/暂停的模板。
    与 batch_restart_templates 不同，此处保留 completed_stages 和中间产物。
    """
    from sqlalchemy import select as sa_select
    from uuid import UUID

    retry_statuses = [
        VideoAIProcessStatus.fail,
        VideoAIProcessStatus.paused,
    ]
    async with SessionLocal() as session:
        stmt = sa_select(VideoAITemplate.id).where(VideoAITemplate.process_status.in_(retry_statuses))
        if owner_id is not None:
            stmt = stmt.where(VideoAITemplate.owner_id == UUID(owner_id))
        if template_ids is not None:
            stmt = stmt.where(VideoAITemplate.id.in_([UUID(tid) for tid in template_ids]))
        rows = (await session.execute(stmt)).scalars().all()

    tids = [str(tid) for tid in rows]
    if not tids:
        return {"total": 0, "success": 0, "fail": 0}

    logger.info("batch_retry started: %d templates", len(tids))
    success_count = 0
    fail_count = 0
    for tid in tids:
        try:
            await resume_template(tid)
            success_count += 1
        except Exception as exc:
            fail_count += 1
            logger.error("[%s] batch_retry failed: %s", tid, exc)

    logger.info("batch_retry enqueued: total=%d success=%d fail=%d", len(tids), success_count, fail_count)
    return {"total": len(tids), "success": success_count, "fail": fail_count}


async def batch_pause_templates(
    owner_id: str | None = None,
    template_ids: list[str] | None = None,
) -> dict:
    """
    批量暂停待处理/运行中的模板。
    队列中尚未启动的 pending 任务会被标记 paused，并在队列消费时跳过。
    """
    from sqlalchemy import select as sa_select
    from uuid import UUID

    pause_statuses = [
        VideoAIProcessStatus.pending,
        VideoAIProcessStatus.understanding,
        VideoAIProcessStatus.imagegen,
        VideoAIProcessStatus.outfit_selecting,
        VideoAIProcessStatus.outfit_detailing,
        VideoAIProcessStatus.product_imagegen,
        VideoAIProcessStatus.outfit_regen,
        VideoAIProcessStatus.splitting,
        VideoAIProcessStatus.face_removing,
        VideoAIProcessStatus.upscaling,
    ]
    async with SessionLocal() as session:
        stmt = sa_select(VideoAITemplate.id).where(VideoAITemplate.process_status.in_(pause_statuses))
        if owner_id is not None:
            stmt = stmt.where(VideoAITemplate.owner_id == UUID(owner_id))
        if template_ids is not None:
            stmt = stmt.where(VideoAITemplate.id.in_([UUID(tid) for tid in template_ids]))
        rows = (await session.execute(stmt)).scalars().all()

    tids = [str(tid) for tid in rows]
    if not tids:
        return {"total": 0, "success": 0, "fail": 0}

    logger.info("batch_pause started: %d templates", len(tids))
    success_count = 0
    fail_count = 0
    for tid in tids:
        try:
            await pause_template(tid)
            success_count += 1
        except Exception as exc:
            fail_count += 1
            logger.error("[%s] batch_pause failed: %s", tid, exc)

    logger.info("batch_pause done: total=%d success=%d fail=%d", len(tids), success_count, fail_count)
    return {"total": len(tids), "success": success_count, "fail": fail_count}


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


async def recover_stuck_templates_on_startup() -> None:
    """启动时恢复中断的模板：
    - pending 且视频已下载完成 → 直接入队
    - pending 且视频还在下载 → 启动协程等下载完再入队
    - 其他运行中状态（understanding/imagegen/...）→ 直接入队（断点续跑）
    - paused 是用户显式暂停状态，启动时保持暂停，不自动恢复
    """
    from sqlalchemy import select as sa_select
    from app.models.video_source import VideoSource

    _RUNNING_STATUSES = [
        VideoAIProcessStatus.understanding,
        VideoAIProcessStatus.imagegen,
        VideoAIProcessStatus.outfit_selecting,
        VideoAIProcessStatus.outfit_detailing,
        VideoAIProcessStatus.product_imagegen,
        VideoAIProcessStatus.outfit_regen,
        # 保留历史状态兼容，避免旧任务卡在已废弃阶段时无法重新入队。
        VideoAIProcessStatus.splitting,
        VideoAIProcessStatus.face_removing,
        VideoAIProcessStatus.upscaling,
    ]

    async with SessionLocal() as session:
        # 运行中状态直接入队
        running_tpls = (await session.execute(
            sa_select(VideoAITemplate).where(
                VideoAITemplate.process_status.in_(_RUNNING_STATUSES)
            )
        )).scalars().all()

        # pending 状态需要检查视频下载状态
        pending_tpls = (await session.execute(
            sa_select(VideoAITemplate).where(
                VideoAITemplate.process_status == VideoAIProcessStatus.pending
            )
        )).scalars().all()

        # 查出所有 pending 模板关联的视频下载状态
        vs_ids = [t.video_source_id for t in pending_tpls if t.video_source_id]
        vs_status_map: dict = {}
        if vs_ids:
            vs_rows = (await session.execute(
                sa_select(VideoSource.id, VideoSource.download_status).where(VideoSource.id.in_(vs_ids))
            )).all()
            vs_status_map = {str(r.id): r.download_status for r in vs_rows}

    total = len(running_tpls) + len(pending_tpls)
    if not total:
        logger.info("No stuck video AI templates found on startup")
        return

    logger.info("Recovering %d stuck video AI templates on startup (%d running, %d pending)",
                total, len(running_tpls), len(pending_tpls))

    # 运行中状态直接断点续跑入队
    for tpl in running_tpls:
        await enqueue_template(str(tpl.id))

    # pending 状态按下载情况处理
    for tpl in pending_tpls:
        download_status = vs_status_map.get(str(tpl.video_source_id)) if tpl.video_source_id else "done"
        if download_status == "done":
            await enqueue_template(str(tpl.id))
        else:
            # 视频还没下载完，启动协程等待
            import asyncio as _asyncio
            _asyncio.get_event_loop().create_task(_wait_download_then_enqueue(str(tpl.id), tpl.video_source_id))

    logger.info("All stuck video AI templates recovery triggered")


async def _wait_download_then_enqueue(tpl_id: str, vs_id) -> None:
    """等视频下载完成后将模板入队（用于重启恢复）。"""
    from app.models.video_source import VideoSource
    from sqlalchemy import select as sa_select
    while True:
        try:
            async with SessionLocal() as session:
                vs = await session.scalar(sa_select(VideoSource).where(VideoSource.id == vs_id))
                if vs is None or vs.download_status == "done":
                    break
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            raise
    async with SessionLocal() as session:
        tpl = await session.get(VideoAITemplate, UUID(tpl_id))
        if not tpl or tpl.process_status != VideoAIProcessStatus.pending:
            logger.info(
                "[%s] skip enqueue after download completion because status is %s",
                tpl_id,
                tpl.process_status.value if tpl else "missing",
            )
            return
    await enqueue_template(tpl_id)
    logger.info("[%s] enqueued after download completion (startup recovery)", tpl_id)


async def stop_video_ai_queue_processor() -> None:
    """
    停止视频 AI 队列处理器

    在应用关闭时调用
    """
    global _queue_processor_task, _persist_worker_task, _shutting_down

    # 标记进程正在关停，避免被取消的管道把状态写成 paused
    _shutting_down = True

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
