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
_CONCURRENCY = 10
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
# 抽帧 & 生图辅助
# =============================================================================

_MAX_VIDEO_SECONDS = 15.0   # 超过此时长只取前 15s
_FRAME_INTERVAL = 1.5       # 每隔 1.5s 取一帧
_MAX_FRAMES = 10            # 最多 10 帧（15 / 1.5 = 10，尾帧抛弃）

_IMAGEGEN_POLL_INTERVAL = 5.0    # 轮询间隔（秒）
_IMAGEGEN_POLL_TIMEOUT = 500.0   # 最长等待时间（秒）


async def _extract_frames(video_url: str, template_id: str) -> list[str]:
    """
    从视频 URL 抽帧，返回帧图片的 base64 data URL 列表（image/jpeg）。
    超过 15s 的视频只截取前 15s，每 1.5s 一帧，抛弃尾帧，最多 10 帧。
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

        # 3. 计算帧时间戳：0, 1.5, 3.0 … 最多 10 帧，抛弃尾帧（确保时间戳 < effective_duration）
        timestamps = []
        t = 0.0
        while t < effective_duration and len(timestamps) < _MAX_FRAMES:
            timestamps.append(t)
            t += _FRAME_INTERVAL
        logger.info("[%s] Extracting %d frames at timestamps: %s", template_id, len(timestamps), timestamps)

        # 4. 用 ffmpeg 批量抽帧
        frames_dir = os.path.join(tmpdir, "frames")
        os.makedirs(frames_dir, exist_ok=True)

        # 用 select filter 精确抽帧（只抽指定时间戳）
        # 先用 -ss 输出单帧，批量并发
        frame_paths = []
        for i, ts in enumerate(timestamps):
            frame_path = os.path.join(frames_dir, f"frame_{i:03d}.jpg")
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-ss", str(ts), "-i", video_path,
                "-vframes", "1", "-q:v", "3", frame_path,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            if os.path.exists(frame_path) and os.path.getsize(frame_path) > 0:
                frame_paths.append(frame_path)
            else:
                logger.warning("[%s] Frame at t=%.1fs failed to extract", template_id, ts)

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


async def _submit_nano2_job(
    *,
    api_base_url: str,
    api_key: str,
    image_urls: list[str],
    prompt: str,
    model: str,
    size: str,
    quality: str,
) -> str:
    """
    提交 Nano2 生图任务，将所有帧图片一口气传入 image_urls，生成一张图，返回 task_id。
    """
    url = f"{api_base_url.rstrip('/')}/v1/images/generations"
    payload: dict = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "quality": quality,
        "image_urls": image_urls,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        if not resp.is_success:
            logger.error("Nano2 submit error: status=%d, body=%s", resp.status_code, resp.text)
        resp.raise_for_status()
        data = resp.json()
    task_id = data.get("id")
    if not task_id:
        raise ValueError(f"Nano2 response missing task id: {data}")
    logger.info("Nano2 task submitted: task_id=%s, image_count=%d", task_id, len(image_urls))
    return task_id


async def _poll_nano2_task(
    *,
    api_base_url: str,
    api_key: str,
    task_id: str,
) -> str:
    """
    轮询 Nano2 任务直到完成，返回结果图片 URL。
    """
    url = f"{api_base_url.rstrip('/')}/v1/tasks/{task_id}"
    deadline = asyncio.get_event_loop().time() + _IMAGEGEN_POLL_TIMEOUT
    while True:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {api_key}"})
            resp.raise_for_status()
            data = resp.json()
        task_status = data.get("status")
        progress = data.get("progress", 0)
        logger.debug("Nano2 task %s: status=%s progress=%d", task_id, task_status, progress)
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


async def _run_imagegen_stage(
    *,
    template_id: str,
    video_url: str,
    api_base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    size: str,
    quality: str,
) -> list[dict]:
    """
    第二阶段完整流程：抽帧 → 上传 CDN → 将所有帧一口气提交给 Nano2 生成一张图 → 轮询结果。
    返回 extracted_shots 列表，每项格式：{"image_url": str, "description": ""}
    """
    # 1. 抽帧
    frame_data_urls = await _extract_frames(video_url, template_id)
    if not frame_data_urls:
        raise ValueError("视频抽帧失败，未获取到任何帧图片")

    # 2. 上传所有帧到 CDN（并发）
    logger.info("[%s] Uploading %d frames to CDN", template_id, len(frame_data_urls))
    upload_results = await asyncio.gather(
        *[_upload_frame_to_cdn(du) for du in frame_data_urls],
        return_exceptions=True,
    )
    frame_cdn_urls = []
    for i, r in enumerate(upload_results):
        if isinstance(r, Exception):
            logger.warning("[%s] Frame %d upload failed: %s", template_id, i, r)
        else:
            frame_cdn_urls.append(r)

    if not frame_cdn_urls:
        raise ValueError("所有帧上传 CDN 失败")
    logger.info("[%s] %d frames uploaded to CDN, submitting single Nano2 job", template_id, len(frame_cdn_urls))

    # 3. 将所有帧一口气提交给 Nano2，生成一张图
    task_id = await _submit_nano2_job(
        api_base_url=api_base_url,
        api_key=api_key,
        image_urls=frame_cdn_urls,
        prompt=prompt,
        model=model,
        size=size,
        quality=quality,
    )
    logger.info("[%s] Nano2 task submitted: %s, polling…", template_id, task_id)

    # 4. 轮询结果
    result_url = await _poll_nano2_task(api_base_url=api_base_url, api_key=api_key, task_id=task_id)

    # 5. 下载 Nano2 结果图并上传到我们的 CDN
    from app.services.upload_service import UpstreamImageUploadService
    cdn_url = result_url
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            dl = await client.get(result_url)
            dl.raise_for_status()
        svc = UpstreamImageUploadService()
        upload_result = await svc.upload_image(dl.content, "image/png", "imagegen_result.png")
        cdn_url = upload_result.url
        logger.info("[%s] Imagegen result uploaded to CDN: %s", template_id, cdn_url[:80])
    except Exception as exc:
        logger.warning("[%s] Failed to re-upload imagegen result to CDN, using original URL: %s", template_id, exc)

    shots = [{"image_url": cdn_url, "description": ""}]
    logger.info("[%s] Imagegen stage done: 1 shot generated", template_id)
    return shots


async def _run_splitting_stage(
    *,
    template_id: str,
    image_url: str,
    splitting_api_url: str = "",
) -> list[dict]:
    """
    第三阶段：调用 segment API 对生图结果进行人物分割，
    将每个 segment 的 base64 上传 CDN，返回 shots 列表。
    每项格式：{"image_url": str, "description": "", "bbox": [...], "confidence": float}
    """
    from app.core.config import settings
    from app.services.upload_service import UpstreamImageUploadService

    base_url = splitting_api_url or settings.splitting_api_base_url
    api_url = f"{base_url.rstrip('/')}/api/segment-models"
    logger.info("[%s] Splitting: calling segment API for image: %s", template_id, image_url[:80])

    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(api_url, json={"image_url": image_url})
        if not resp.is_success:
            logger.error("[%s] Segment API error: status=%d, body=%s", template_id, resp.status_code, resp.text[:300])
        resp.raise_for_status()
        data = resp.json()

    if not data.get("success"):
        raise ValueError(f"Segment API returned success=false: {data.get('message', '')}")

    segments: list[dict] = data.get("segments", [])
    if not segments:
        raise ValueError("Segment API returned no segments")

    logger.info("[%s] Splitting: %d segments received, uploading to CDN", template_id, len(segments))

    svc = UpstreamImageUploadService()
    shots = []
    for seg in segments:
        b64 = seg.get("image_base64", "")
        if not b64:
            logger.warning("[%s] Segment index=%s has no image_base64, skipping", template_id, seg.get("index"))
            continue
        try:
            content = base64.b64decode(b64)
            result = await svc.upload_image(content, "image/png", f"segment_{seg.get('index', 0)}.png")
            shots.append({
                "image_url": result.url,
                "description": "",
                "bbox": seg.get("bbox"),
                "confidence": seg.get("confidence"),
                "image_base64": b64,  # 保留 base64 供第四阶段直接使用，避免重复下载
            })
        except Exception as exc:
            logger.warning("[%s] Segment index=%s upload failed: %s", template_id, seg.get("index"), exc)

    if not shots:
        raise ValueError("所有 segment 上传 CDN 失败")

    logger.info("[%s] Splitting stage done: %d shots uploaded", template_id, len(shots))
    return shots


async def _run_face_removing_stage(
    *,
    template_id: str,
    shots: list[dict],
    face_removing_api_url: str = "",
    score_thresh: float = 0.3,
    margin_scale: float = 0.2,
    head_top_ratio: float = 0.7,
) -> list[dict]:
    """
    第四阶段：对每张 shot 图片调用去脸 API，返回更新后的 shots 列表。
    processedUrl 替换原 image_url。
    """
    base_url = face_removing_api_url or "http://34.86.216.234:8001"
    api_url = f"{base_url.rstrip('/')}/api/v1/style-outfits/processBodyShape"
    logger.info("[%s] Face-removing: processing %d shots, api=%s", template_id, len(shots), api_url)

    from app.services.upload_service import UpstreamImageUploadService
    upload_svc = UpstreamImageUploadService()

    result_shots = []
    async with httpx.AsyncClient(timeout=300.0) as client:
        for i, shot in enumerate(shots):
            # 优先用分割阶段已有的 base64，避免重复下载
            image_b64 = shot.get("image_base64", "")
            if not image_b64:
                image_url = shot.get("image_url", "")
                if not image_url:
                    result_shots.append(shot)
                    continue
                logger.info("[%s] Face-removing shot[%d]: no base64, downloading from %s", template_id, i, image_url[:80])
                dl_resp = await client.get(image_url)
                dl_resp.raise_for_status()
                image_b64 = base64.b64encode(dl_resp.content).decode()

            req_payload = {
                "imageBase64": image_b64,
                "userId": "default",
                "scoreThresh": score_thresh,
                "marginScale": margin_scale,
                "headTopRatio": head_top_ratio,
            }
            logger.info("[%s] Face-removing shot[%d]: calling API", template_id, i)
            resp = await client.post(api_url, json=req_payload)
            if not resp.is_success:
                logger.error("[%s] Face-removing shot[%d] API error: status=%d body=%s", template_id, i, resp.status_code, resp.text[:300])
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 0 or not data.get("success"):
                raise ValueError(f"Face-removing API shot[{i}] error: {data.get('message', '')}")

            processed_url = data["data"]["processedUrl"]
            logger.info("[%s] Face-removing shot[%d] processedUrl: %s", template_id, i, processed_url[:80])

            # 下载处理后图片并上传到我们的 CDN
            dl2 = await client.get(processed_url)
            dl2.raise_for_status()
            upload_result = await upload_svc.upload_image(dl2.content, "image/png", f"face_removed_{i}.png")
            cdn_url = upload_result.url
            logger.info("[%s] Face-removing shot[%d] uploaded to CDN: %s", template_id, i, cdn_url[:80])

            # 去掉 image_base64 字段，不存入最终结果
            shot_out = {k: v for k, v in shot.items() if k != "image_base64"}
            result_shots.append({**shot_out, "image_url": cdn_url})

    logger.info("[%s] Face-removing stage done: %d shots", template_id, len(result_shots))
    for i, s in enumerate(result_shots):
        logger.info("[%s]   shot[%d] final image_url=%s", template_id, i, s.get("image_url", "")[:120])
    return result_shots


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
                    imagegen_model = pipeline_cfg.imagegen_model or "gemini-3.1-flash-image-preview"
                    imagegen_prompt = pipeline_cfg.imagegen_prompt or "根据参考图生成同款风格图片"
                    imagegen_size = pipeline_cfg.imagegen_size or "9:16"
                    imagegen_quality = pipeline_cfg.imagegen_quality or "2K"
                    splitting_api_url = pipeline_cfg.splitting_api_url or ""
                    face_removing_api_url = pipeline_cfg.face_removing_api_url or ""
                    face_removing_score_thresh = pipeline_cfg.face_removing_score_thresh
                    face_removing_margin_scale = pipeline_cfg.face_removing_margin_scale
                    face_removing_head_top_ratio = pipeline_cfg.face_removing_head_top_ratio
                else:
                    understand_model = "gemini-3.1-pro-preview"
                    understand_prompt = "请描述这个视频的内容，包括场景、人物、服装风格等。"
                    understand_temperature = 0.3
                    imagegen_model = "gemini-3.1-flash-image-preview"
                    imagegen_prompt = "根据参考图生成同款风格图片"
                    imagegen_size = "9:16"
                    imagegen_quality = "2K"
                    splitting_api_url = ""
                    face_removing_api_url = ""
                    face_removing_score_thresh = 0.3
                    face_removing_margin_scale = 0.2
                    face_removing_head_top_ratio = 0.7
            # 获取当前 state（可能带有已完成阶段信息）
            state = video_ai_states.setdefault(template_id, _new_state(template_id, VideoAIProcessStatus.pending))
            completed_stages: list[str] = state.get("completed_stages") or []

            if not api_key:
                raise ValueError("系统未配置 EvoLink API Key，请前往【系统设置】进行配置。")

            # ========== 步骤 1: 视频整体理解 ==========
            if "understanding" in completed_stages:
                prompt_description = state.get("prompt_description") or ""
                logger.info("[%s] understanding skipped (already completed), prompt_description=%d chars",
                            template_id, len(prompt_description))
            else:
                _set_status(template_id, VideoAIProcessStatus.understanding)
                logger.info("[%s] understanding started", template_id)

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
                if "understanding" not in state.get("completed_stages", []):
                    state.setdefault("completed_stages", []).append("understanding")
                _mark_dirty(template_id)

                # 立即持久化 prompt_description 到数据库
                async with SessionLocal() as session:
                    tpl = await session.get(VideoAITemplate, uuid_val)
                    if tpl:
                        tpl.prompt_description = prompt_description
                        await session.commit()

            # ========== 步骤 2: 抽帧生图 ==========
            if "imagegen" in completed_stages:
                shots = state.get("extracted_shots") or []
                logger.info("[%s] imagegen skipped (already completed), %d shots", template_id, len(shots))
            else:
                _set_status(template_id, VideoAIProcessStatus.imagegen)
                logger.info("[%s] imagegen stage started", template_id)
                shots = await _run_imagegen_stage(
                    template_id=template_id,
                    video_url=video_url,
                    api_base_url=api_base_url,
                    api_key=api_key,
                    model=imagegen_model,
                    prompt=imagegen_prompt,
                    size=imagegen_size,
                    quality=imagegen_quality,
                )
                state = video_ai_states.setdefault(template_id, _new_state(template_id, VideoAIProcessStatus.imagegen))
                state["extracted_shots"] = shots
                state["updated_at"] = _utcnow_iso()
                if "imagegen" not in state.get("completed_stages", []):
                    state.setdefault("completed_stages", []).append("imagegen")
                _mark_dirty(template_id)

                # 持久化 extracted_shots 到数据库，同时快照到 extra.imagegen_shots
                async with SessionLocal() as session:
                    tpl = await session.get(VideoAITemplate, uuid_val)
                    if tpl:
                        tpl.extracted_shots = shots
                        extra = dict(tpl.extra or {})
                        extra["imagegen_shots"] = shots
                        tpl.extra = extra
                        await session.commit()
                logger.info("[%s] imagegen stage completed, %d shots saved", template_id, len(shots))

            # ========== 步骤 3: 拆分图片 ==========
            if "splitting" in completed_stages:
                split_shots = state.get("extracted_shots") or []
                logger.info("[%s] splitting skipped (already completed), %d shots", template_id, len(split_shots))
            else:
                _set_status(template_id, VideoAIProcessStatus.splitting)
                # imagegen 产出的是 1 张图，取第一张的 image_url 进行拆分
                imagegen_image_url = shots[0]["image_url"] if shots else None
                if not imagegen_image_url:
                    raise ValueError("imagegen 未产出图片，无法进行拆分")
                logger.info("[%s] splitting stage started, image=%s", template_id, imagegen_image_url[:80])
                split_shots = await _run_splitting_stage(
                    template_id=template_id,
                    image_url=imagegen_image_url,
                    splitting_api_url=splitting_api_url,
                )
                state = video_ai_states.setdefault(template_id, _new_state(template_id, VideoAIProcessStatus.splitting))
                state["extracted_shots"] = split_shots  # 内存保留 base64 供步骤4使用
                state["updated_at"] = _utcnow_iso()
                if "splitting" not in state.get("completed_stages", []):
                    state.setdefault("completed_stages", []).append("splitting")
                _mark_dirty(template_id)

                # 立即持久化到数据库 + 让前端 polling 立刻能看到结果，同时快照到 extra.splitting_shots
                # 存入 DB 和前端展示时去掉 image_base64（只在内存中传给步骤4）
                split_shots_for_db = [{k: v for k, v in s.items() if k != "image_base64"} for s in split_shots]
                async with SessionLocal() as session:
                    tpl = await session.get(VideoAITemplate, uuid_val)
                    if tpl:
                        tpl.extracted_shots = split_shots_for_db
                        extra = dict(tpl.extra or {})
                        extra["splitting_shots"] = split_shots_for_db
                        tpl.extra = extra
                        await session.commit()
                logger.info("[%s] splitting stage completed, %d shots saved", template_id, len(split_shots))

            # ========== 步骤 4: 去脸 ==========
            if "face_removing" in completed_stages:
                final_shots = state.get("extracted_shots") or split_shots
                logger.info("[%s] face_removing skipped (already completed), %d shots", template_id, len(final_shots))
            else:
                _set_status(template_id, VideoAIProcessStatus.face_removing)
                logger.info("[%s] face_removing stage started, %d shots", template_id, len(split_shots))
                final_shots = await _run_face_removing_stage(
                    template_id=template_id,
                    shots=split_shots,
                    face_removing_api_url=face_removing_api_url,
                    score_thresh=face_removing_score_thresh,
                    margin_scale=face_removing_margin_scale,
                    head_top_ratio=face_removing_head_top_ratio,
                )
                state = video_ai_states.setdefault(template_id, _new_state(template_id, VideoAIProcessStatus.face_removing))
                state["extracted_shots"] = final_shots
                state["updated_at"] = _utcnow_iso()
                if "face_removing" not in state.get("completed_stages", []):
                    state.setdefault("completed_stages", []).append("face_removing")
                _mark_dirty(template_id)

                # 持久化到数据库，同时快照到 extra.face_removing_shots
                async with SessionLocal() as session:
                    tpl = await session.get(VideoAITemplate, uuid_val)
                    if tpl:
                        tpl.extracted_shots = final_shots
                        extra = dict(tpl.extra or {})
                        extra["face_removing_shots"] = final_shots
                        tpl.extra = extra
                        await session.commit()
                logger.info("[%s] face_removing stage completed, %d shots saved", template_id, len(final_shots))

            # ========== 步骤 N: 成功 ==========
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


async def enqueue_template(template_id: str, *, clear_stages: bool = False) -> None:
    """
    将模板加入队列并标记为等待中。

    Args:
        template_id: 模板 ID
        clear_stages: 为 True 时清空 completed_stages，从头重跑；默认 False（断点续跑）
    """
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
