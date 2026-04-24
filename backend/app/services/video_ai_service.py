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

from app.services.ai_api import call_gemini_api
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
# pipeline 完成后需要同步 shots 到 video_tasks 的模板 ID 集合
_sync_shots_on_success: set[str] = set()

# 队列处理器任务和持久化任务
_queue_processor_task: asyncio.Task | None = None
_persist_worker_task: asyncio.Task | None = None

# 并发数：同时处理的最大任务数
_CONCURRENCY = 5
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
        "completed_stages": [],  # 已完成的阶段列表，用于断点续跑
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
        product_cdn_urls = [p["product_image_url"] for p in solo_products if p.get("product_image_url")]

        new_outfit_url = outfit_image_url
        if product_cdn_urls:
            r_prompt = prompt.strip()
            if not r_prompt:
                r_prompt = default_prompt.format(outfit_style=outfit_style)
            else:
                r_prompt = r_prompt.replace("{outfit_style}", outfit_style)
            try:
                img_bytes = await generate_image(
                    model_name=model,
                    prompt=r_prompt,
                    image_urls=product_cdn_urls,
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


async def _sync_task_shots(template_id: str, uuid_val: UUID, final_outfits: list[dict]) -> None:
    """
    将 final_outfits 的造型图同步回关联该模板的所有 video_tasks.shots。
    - has_face=True：shots[0] 是人脸图，保留不动，从 shots[1:] 开始替换为造型图
    - has_face=False：整个 shots 替换为造型图
    """
    from sqlalchemy import select as sa_select
    from app.models.video_task import VideoTask

    outfit_shots = [
        {"image_url": o["image_url"], "outfit_style": o.get("outfit_style", "")}
        for o in final_outfits
        if o.get("image_url")
    ]
    if not outfit_shots:
        return

    async with SessionLocal() as session:
        tasks = (await session.execute(
            sa_select(VideoTask).where(VideoTask.template_id == uuid_val)
        )).scalars().all()

        for task in tasks:
            existing = list(task.shots or [])
            if task.has_face and existing:
                # 保留首位人脸图，其余替换为造型图
                task.shots = [existing[0], *outfit_shots]
            else:
                task.shots = outfit_shots

        await session.commit()

    logger.info("[%s] synced shots to %d tasks (%d outfits)", template_id, len(tasks), len(outfit_shots))


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

    流程：理解 → 提取 → 下载 → 上传 → 成功/失败

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
                    understand_model = pipeline_cfg.understand_model or "gemini-3.1-pro-preview"
                    understand_prompt = pipeline_cfg.understand_prompt or "请描述这个视频的内容，包括场景、人物、服装风格等。"
                    understand_temperature = pipeline_cfg.understand_temperature
                    # 步骤3：穿搭识别
                    outfit_select_model = pipeline_cfg.outfit_select_model or "gemini-3.1-pro-preview"
                    outfit_select_prompt = pipeline_cfg.outfit_select_prompt or ""
                    outfit_select_temperature = pipeline_cfg.outfit_select_temperature
                    # 步骤4a：穿搭单品理解
                    outfit_detail_model = pipeline_cfg.outfit_detail_model or "gemini-3.1-pro-preview"
                    outfit_detail_prompt = pipeline_cfg.outfit_detail_prompt or ""
                    outfit_detail_temperature = pipeline_cfg.outfit_detail_temperature
                    # 步骤4b：单品图生成
                    product_imagegen_model = pipeline_cfg.product_imagegen_model or "gemini-3.1-flash-image-preview"
                    product_imagegen_prompt = pipeline_cfg.product_imagegen_prompt or ""
                    product_imagegen_size = pipeline_cfg.product_imagegen_size or "1:1"
                    product_imagegen_quality = pipeline_cfg.product_imagegen_quality or "2K"
                    # 步骤4c：新造型图生成
                    outfit_regen_model = pipeline_cfg.outfit_regen_model or "gemini-3.1-flash-image-preview"
                    outfit_regen_prompt = pipeline_cfg.outfit_regen_prompt or ""
                    outfit_regen_size = pipeline_cfg.outfit_regen_size or "9:16"
                    outfit_regen_quality = pipeline_cfg.outfit_regen_quality or "2K"
                else:
                    understand_model = "gemini-3.1-pro-preview"
                    understand_prompt = "请描述这个视频的内容，包括场景、人物、服装风格等。"
                    understand_temperature = 0.3
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
            completed_stages: list[str] = state.get("completed_stages") or []

            # 断点续跑：从 DB extra 字段恢复中间阶段数据（内存 state 可能已清空）
            async with SessionLocal() as session:
                _tpl_for_restore = await session.get(VideoAITemplate, uuid_val)
                _extra = dict(_tpl_for_restore.extra or {}) if _tpl_for_restore else {}
            if "imagegen" in completed_stages and not state.get("frame_shots"):
                state["frame_shots"] = _extra.get("frame_shots") or []
            if "outfit_selecting" in completed_stages and not state.get("outfit_shots"):
                state["outfit_shots"] = _extra.get("outfit_shots") or []
            if "outfit_regen" in completed_stages and not state.get("final_outfits"):
                state["final_outfits"] = _extra.get("final_outfits") or []
            if "outfit_detailing" in completed_stages and not state.get("outfit_detailing_progress"):
                state["outfit_detailing_progress"] = _extra.get("outfit_detailing_progress") or []

            # ========== 步骤 1: 视频整体理解（最多重试 3 次）==========
            if "understanding" in completed_stages:
                prompt_description = state.get("prompt_description") or ""
                logger.info("[%s] understanding skipped (already completed), prompt_description=%d chars",
                            template_id, len(prompt_description))
            else:
                _set_status(template_id, VideoAIProcessStatus.understanding)
                logger.info("[%s] understanding started", template_id)

                prompt_description = await call_gemini_api(
                    model_name=understand_model,
                    video_url=video_url,
                    prompt=understand_prompt,
                    temperature=understand_temperature,
                )

                state = video_ai_states.setdefault(template_id, _new_state(template_id, VideoAIProcessStatus.understanding))
                state["prompt_description"] = prompt_description
                state["updated_at"] = _utcnow_iso()
                if "understanding" not in state.get("completed_stages", []):
                    state.setdefault("completed_stages", []).append("understanding")
                _mark_dirty(template_id)

                # 立即持久化 prompt_description 到数据库
                async with SessionLocal() as session:
                    tpl = await session.get(VideoAITemplate, uuid_val)
                    if tpl:
                        tpl.prompt_description = prompt_description
                        tpl.process_state = json.dumps(state, ensure_ascii=False)
                        await session.commit()

            # ========== 步骤 2: 抽帧并上传 CDN（1s一帧，最多重试 3 次）==========
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

            # ========== 步骤 3: Gemini 识别 Unique 穿搭（最多重试 3 次）==========
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

            # ========== 步骤 4a: 穿搭单品理解（每个穿搭 → outfit_style + solo_products）==========
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

            # ========== 步骤 4b: 单品图生成 ==========
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

            # ========== 步骤 4c: 新造型图生成 ==========
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
                extracted_shots_final = [{"image_url": o["image_url"], "outfit_style": o.get("outfit_style", "")} for o in final_outfits]
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
                if _final_outfits:
                    await _sync_task_shots(template_id, uuid_val, _final_outfits)

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
    从阶段二重跑：保留阶段一（视频理解/prompt_description），
    清除 imagegen 及之后的所有阶段数据，重新执行抽帧生图→穿搭识别→…流程。
    """
    # 先停止正在运行的任务
    task = video_ai_worker_tasks.get(template_id)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # 确保内存中有 state（从 DB 恢复）
    if template_id not in video_ai_states:
        try:
            uuid_val = UUID(template_id)
            async with SessionLocal() as session:
                tpl = await session.get(VideoAITemplate, uuid_val)
                if tpl and tpl.process_state:
                    video_ai_states[template_id] = json.loads(tpl.process_state)
        except Exception as exc:
            logger.warning("[%s] restart_from_stage2: failed to restore state: %s", template_id, exc)

    state = video_ai_states.setdefault(template_id, _new_state(template_id, VideoAIProcessStatus.pending))

    # 只保留 understanding 阶段，清除其余
    completed = state.get("completed_stages") or []
    state["completed_stages"] = [s for s in completed if s == "understanding"]
    state["frame_shots"] = []
    state["outfit_shots"] = []
    state["outfit_detailing_progress"] = []
    state["product_gen_results"] = []
    state["final_outfits"] = []
    state["extracted_shots"] = []
    state["status"] = VideoAIProcessStatus.pending.value
    state["error_message"] = ""
    state["updated_at"] = _utcnow_iso()
    _mark_dirty(template_id)

    # 同步清理 DB extra 字段（保留 understanding 之外的快照数据不需要了）
    try:
        uuid_val = UUID(template_id)
        async with SessionLocal() as session:
            tpl = await session.get(VideoAITemplate, uuid_val)
            if tpl:
                tpl.process_status = VideoAIProcessStatus.pending
                tpl.process_error = None
                tpl.extracted_shots = []
                extra = dict(tpl.extra or {})
                for key in ("frame_shots", "outfit_shots", "outfit_detailing_progress",
                            "product_gen_results", "final_outfits"):
                    extra.pop(key, None)
                tpl.extra = extra
                tpl.process_state = json.dumps(state, ensure_ascii=False)
                await session.commit()
    except Exception as exc:
        logger.warning("[%s] restart_from_stage2: DB cleanup failed: %s", template_id, exc)

    dirty_video_ai_ids.discard(template_id)
    _ensure_persist_worker()
    await video_ai_queue.put(template_id)
    logger.info("[%s] restart_from_stage2 enqueued (keeping understanding stage)", template_id)


async def reanalyze_template(template_id: str, max_retries: int = 3) -> None:
    """
    仅重新执行视频理解（understanding）步骤，更新 prompt_description，
    不跑后续的抽帧、穿搭识别和生成阶段。
    失败自动重试最多 max_retries 次。
    """
    from uuid import UUID
    from app.services.pipeline_settings_service import get_or_create_pipeline_settings
    from app.services.ai_api import call_gemini_api
    from app.models.video_source import VideoSource

    uuid_val = UUID(template_id)

    async with SessionLocal() as session:
        tpl = await session.get(VideoAITemplate, uuid_val)
        if not tpl:
            raise ValueError("模板不存在")

        # 加载视频 URL
        video_url: str | None = None
        if tpl.video_source_id:
            vs = await session.get(VideoSource, tpl.video_source_id)
            if vs:
                video_url = vs.local_video_url or vs.video_url
        if not video_url:
            raise ValueError("视频地址不可用")

        # 加载配置
        if tpl.owner_id is not None:
            pipeline_cfg = await get_or_create_pipeline_settings(session, owner_id=tpl.owner_id)
            understand_model = pipeline_cfg.understand_model or "gemini-3.1-pro-preview"
            understand_prompt = pipeline_cfg.understand_prompt or "请描述这个视频的内容，包括场景、人物、服装风格等。"
            understand_temperature = pipeline_cfg.understand_temperature
        else:
            understand_model = "gemini-3.1-pro-preview"
            understand_prompt = "请描述这个视频的内容，包括场景、人物、服装风格等。"
            understand_temperature = 0.3

    # 带重试的 AI 调用（在 session 外执行，避免长时间占用连接）
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            prompt_description = await call_gemini_api(
                model_name=understand_model,
                video_url=video_url,
                prompt=understand_prompt,
                temperature=understand_temperature,
            )
            break
        except Exception as exc:
            last_exc = exc
            logger.warning("[%s] reanalyze attempt %d/%d failed: %s", template_id, attempt, max_retries, exc)
            if attempt < max_retries:
                await asyncio.sleep(2 ** attempt)
    else:
        raise last_exc  # type: ignore[misc]

    # 更新数据库
    async with SessionLocal() as session:
        from sqlalchemy import select as sa_select, update as sa_update
        from app.models.video_task import VideoTask

        tpl = await session.get(VideoAITemplate, uuid_val)
        if tpl:
            tpl.prompt_description = prompt_description
            await session.commit()

        # 将新 prompt 回写到关联的 video_tasks，并标记 is_prompt_updated=True
        await session.execute(
            sa_update(VideoTask)
            .where(VideoTask.template_id == uuid_val)
            .values(prompt=prompt_description, is_prompt_updated=True)
        )
        await session.commit()

    # 同步更新内存状态（如果存在的话）
    if template_id in video_ai_states:
        video_ai_states[template_id]["prompt_description"] = prompt_description
        video_ai_states[template_id]["updated_at"] = _utcnow_iso()

    logger.info("[%s] reanalyze completed, prompt_description=%d chars", template_id, len(prompt_description))


async def batch_reanalyze_templates(
    owner_id: str | None = None,
    concurrency: int = 5,
    template_ids: list[str] | None = None,
) -> dict:
    """
    后台批量重新分析所有 success 状态的模板。
    使用 Semaphore 控制并发，每个模板内部自带重试。
    如果传入 template_ids，则只分析指定的模板（仍过滤 success 状态）。

    Returns:
        {"total": N, "success": N, "fail": N, "errors": {template_id: error_msg}}
    """
    from sqlalchemy import select as sa_select
    from uuid import UUID

    # 1. 查询目标模板
    async with SessionLocal() as session:
        stmt = sa_select(VideoAITemplate.id).where(
            VideoAITemplate.process_status == VideoAIProcessStatus.success
        )
        if owner_id is not None:
            stmt = stmt.where(VideoAITemplate.owner_id == UUID(owner_id))
        if template_ids is not None:
            stmt = stmt.where(VideoAITemplate.id.in_([UUID(tid) for tid in template_ids]))
        rows = (await session.execute(stmt)).scalars().all()

    template_ids = [str(tid) for tid in rows]
    if not template_ids:
        return {"total": 0, "success": 0, "fail": 0, "errors": {}}

    logger.info("batch_reanalyze started: %d templates, concurrency=%d", len(template_ids), concurrency)

    # 2. 并发执行，Semaphore 限流
    sem = asyncio.Semaphore(_CONCURRENCY)
    results: dict[str, str | None] = {}  # template_id -> error_msg or None

    async def _worker(tid: str) -> None:
        async with sem:
            try:
                await reanalyze_template(tid)
                results[tid] = None
            except Exception as exc:
                results[tid] = str(exc)
                logger.error("[%s] batch_reanalyze failed: %s", tid, exc)

    await asyncio.gather(*[_worker(tid) for tid in template_ids])

    success_count = sum(1 for v in results.values() if v is None)
    fail_count = sum(1 for v in results.values() if v is not None)
    errors = {k: v for k, v in results.items() if v is not None}

    logger.info("batch_reanalyze done: total=%d success=%d fail=%d", len(template_ids), success_count, fail_count)
    return {"total": len(template_ids), "success": success_count, "fail": fail_count, "errors": errors}


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


async def batch_restart_stage2_templates(owner_id: str | None = None) -> dict:
    """
    后台批量对所有 success 状态的模板执行 restart_from_stage2（保留视频理解，从阶段2抽帧重跑）。
    Returns:
        {"total": N, "success": N, "fail": N}
    """
    from sqlalchemy import select as sa_select
    from uuid import UUID

    async with SessionLocal() as session:
        stmt = sa_select(VideoAITemplate.id).where(
            VideoAITemplate.process_status == VideoAIProcessStatus.success
        )
        if owner_id is not None:
            stmt = stmt.where(VideoAITemplate.owner_id == UUID(owner_id))
        rows = (await session.execute(stmt)).scalars().all()

    tids = [str(tid) for tid in rows]
    if not tids:
        return {"total": 0, "success": 0, "fail": 0}

    logger.info("batch_restart_stage2 started: %d templates", len(tids))
    sem = asyncio.Semaphore(_CONCURRENCY)
    success_count = 0
    fail_count = 0

    async def _worker(tid: str) -> None:
        nonlocal success_count, fail_count
        async with sem:
            try:
                await restart_from_stage2(tid)
                success_count += 1
            except Exception as exc:
                fail_count += 1
                logger.error("[%s] batch_restart_stage2 failed: %s", tid, exc)

    await asyncio.gather(*[_worker(tid) for tid in tids])
    logger.info("batch_restart_stage2 done: total=%d success=%d fail=%d", len(tids), success_count, fail_count)
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
    """
    from sqlalchemy import select as sa_select
    from app.models.video_source import VideoSource

    _RUNNING_STATUSES = [
        VideoAIProcessStatus.paused,       # 重启时被取消导致的暂停，自动恢复
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
    await enqueue_template(tpl_id)
    logger.info("[%s] enqueued after download completion (startup recovery)", tpl_id)


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
