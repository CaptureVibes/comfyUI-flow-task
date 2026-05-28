from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from uuid import UUID, uuid4

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

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
# pipeline 失败时需要把指定 video_tasks 标记为 abandoned 的映射：
# {template_id: [video_task_id, ...]}
# 由 daily-tasks "一键重试" 通过 batch_restart_templates 写入；
# _sync_task_shots 在管道终态统一处理（成功仅同步 shots，失败 abandoned 关联任务）。
_abandon_task_ids_on_fail: dict[str, list[str]] = {}

# 队列处理器任务和持久化任务
_queue_processor_task: asyncio.Task | None = None
_persist_worker_task: asyncio.Task | None = None
# 进程关停标志：True 时管道被取消不写 paused，保留运行中状态以便重启后续跑
_shutting_down: bool = False

# 并发数：同时处理的最大 pipeline 数（pipeline 大头是 Gemini/外部 API，I/O 密集，可较高）
_CONCURRENCY = 10
# 抽帧 / 拼接 / ffprobe 等"轻量"ffmpeg 子进程（秒级）：用一个稍宽的 semaphore
_FFMPEG_CONCURRENCY = 2
_ffmpeg_semaphore: asyncio.Semaphore | None = None
# 重量级 libx264 压缩单独一个 semaphore，避免长时间压缩把抽帧锁死
# （单条压缩可达 5~10 分钟，跟秒级抽帧共用 Semaphore(2) 会让 AI 模板永久排队）
_FFMPEG_HEAVY_CONCURRENCY = 1
_ffmpeg_heavy_semaphore: asyncio.Semaphore | None = None

# 抽帧后并发上传 CDN 的上限：抽帧通常 30+ 帧，全部同时打 CDN 容易触发限流→全员重试
_FRAME_UPLOAD_CONCURRENCY = 8
# 单帧上传整体预算（含内部重试），超过则放弃，避免 gather 被一帧拖死
_FRAME_UPLOAD_BUDGET_SEC = 90.0
# 整个 imagegen 阶段的兜底超时（抽帧 + 全部上传），到点抛错让模板进 failed
_IMAGEGEN_STAGE_TIMEOUT_SEC = 600.0
_frame_upload_semaphore: asyncio.Semaphore | None = None

# 抽帧前下载视频的并发上限和整体超时：避免 10 个 pipeline 同时打 CDN，且
# httpx 的 timeout 实际是 per-IO read timeout，慢吐字节可以挂无限久 → 用
# asyncio.wait_for 强制总时长上限
_VIDEO_DOWNLOAD_CONCURRENCY = 4
_VIDEO_DOWNLOAD_TIMEOUT_SEC = 120.0
_video_download_semaphore: asyncio.Semaphore | None = None


def _get_ffmpeg_semaphore() -> asyncio.Semaphore:
    """轻量 ffmpeg/ffprobe 任务（秒级）的并发信号量。"""
    global _ffmpeg_semaphore
    if _ffmpeg_semaphore is None:
        _ffmpeg_semaphore = asyncio.Semaphore(_FFMPEG_CONCURRENCY)
    return _ffmpeg_semaphore


def _get_ffmpeg_heavy_semaphore() -> asyncio.Semaphore:
    """重量级 libx264 压缩等长任务（分钟级）的独立信号量，不与轻量任务共用。"""
    global _ffmpeg_heavy_semaphore
    if _ffmpeg_heavy_semaphore is None:
        _ffmpeg_heavy_semaphore = asyncio.Semaphore(_FFMPEG_HEAVY_CONCURRENCY)
    return _ffmpeg_heavy_semaphore


def _get_frame_upload_semaphore() -> asyncio.Semaphore:
    global _frame_upload_semaphore
    if _frame_upload_semaphore is None:
        _frame_upload_semaphore = asyncio.Semaphore(_FRAME_UPLOAD_CONCURRENCY)
    return _frame_upload_semaphore


def _get_video_download_semaphore() -> asyncio.Semaphore:
    global _video_download_semaphore
    if _video_download_semaphore is None:
        _video_download_semaphore = asyncio.Semaphore(_VIDEO_DOWNLOAD_CONCURRENCY)
    return _video_download_semaphore


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
    from app.utils.tmp_storage import disk_tempdir, ensure_free_space
    # 抽帧前预检：1 个视频 + 几十帧 jpg，给 500MB 余量足够
    ensure_free_space(min_bytes=500 * 1024 * 1024, label=f"frame_extract({template_id})")

    with disk_tempdir(prefix=f"vai_{template_id[:8]}_") as tmpdir:
        video_path = os.path.join(tmpdir, "video.mp4")

        # 1. 下载视频 —— 受 _VIDEO_DOWNLOAD_CONCURRENCY 限流，外层 wait_for 兜底强制总时长。
        # GCS（gs:// 或 storage.googleapis.com）走 SDK（私有桶可用），其它走 httpx 流式下载。
        logger.info("[%s] Downloading video for frame extraction: %s", template_id, video_url[:80])

        from app.utils.gcs_download import download_url_to_local

        async with _get_video_download_semaphore():
            try:
                downloaded_bytes = await asyncio.wait_for(
                    download_url_to_local(video_url, video_path, timeout=30.0),
                    timeout=_VIDEO_DOWNLOAD_TIMEOUT_SEC,
                )
            except asyncio.TimeoutError as exc:
                raise RuntimeError(
                    f"video download timeout after {_VIDEO_DOWNLOAD_TIMEOUT_SEC:.0f}s "
                    f"for template {template_id}, url={video_url[:120]}"
                ) from exc
        logger.info(
            "[%s] Downloaded %.1f MB", template_id, downloaded_bytes / 1024 / 1024,
        )

        # 2. 用 ffprobe 获取视频时长（带大 probesize/analyzeduration，应对部分容器需要更多字节才能识别流）
        # -threads 1：单进程占 1 核；外加全局 ffmpeg 信号量，限制同时运行的 ffmpeg/ffprobe 数量
        async with _get_ffmpeg_semaphore():
            probe_proc = await asyncio.create_subprocess_exec(
                "ffprobe", "-v", "error",
                "-threads", "1",
                "-probesize", "50M", "-analyzeduration", "100M",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", video_path,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            try:
                probe_out, probe_err = await asyncio.wait_for(probe_proc.communicate(), timeout=60.0)
            except asyncio.TimeoutError:
                probe_proc.kill()
                await probe_proc.wait()
                raise RuntimeError(f"ffprobe timeout after 60s for template {template_id}")
        try:
            duration = float(probe_out.decode().strip())
        except ValueError:
            duration = _MAX_VIDEO_SECONDS
            err_tail = probe_err.decode(errors="replace")[-300:] if probe_err else ""
            logger.warning("[%s] ffprobe duration parse failed (using fallback=%.1fs); ffprobe stderr: %s",
                           template_id, _MAX_VIDEO_SECONDS, err_tail)
        effective_duration = min(duration, _MAX_VIDEO_SECONDS)
        logger.info("[%s] Video duration=%.1fs, effective=%.1fs", template_id, duration, effective_duration)

        # 3. 单次 ffmpeg 调用顺序抽帧：用 fps 过滤器代替逐帧 seek，避免 "no decoder found for: none"
        #    类问题（部分容器 codec 探测不稳定时，前置 -ss 会失败）。
        file_size = os.path.getsize(video_path) if os.path.exists(video_path) else 0
        logger.info("[%s] Downloaded video file size: %d bytes", template_id, file_size)

        frames_dir = os.path.join(tmpdir, "frames")
        os.makedirs(frames_dir, exist_ok=True)
        out_pattern = os.path.join(frames_dir, "frame_%03d.jpg")
        # interval=1 → fps=1；interval=0.5 → fps=2，以此类推
        fps_value = 1.0 / max(interval, 0.001)

        async def _run_extract(input_path: str) -> tuple[int, str]:
            cmd = [
                "ffmpeg", "-y",
                "-threads", "1",
                "-probesize", "50M", "-analyzeduration", "100M",
                "-t", str(effective_duration),  # 限制只取前 N 秒
                "-i", input_path,
                "-vf", f"fps={fps_value}",
                "-q:v", "3",
                "-start_number", "0",
                out_pattern,
            ]
            async with _get_ffmpeg_semaphore():
                proc = await asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                try:
                    # 15s 短视频抽帧正常 < 5s；给 60s 上限避免 ffmpeg 卡死把 CPU 撑满
                    _, err = await asyncio.wait_for(proc.communicate(), timeout=60.0)
                    return proc.returncode or 0, (err.decode(errors="replace") if err else "")
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                    logger.error("[%s] ffmpeg extraction timeout (60s) for %s, killed", template_id, input_path)
                    return -9, "TIMEOUT_KILLED"

        rc, stderr_text = await _run_extract(video_path)
        # 收集生成的帧文件
        frame_paths = sorted(
            os.path.join(frames_dir, fn)
            for fn in os.listdir(frames_dir) if fn.startswith("frame_") and fn.endswith(".jpg")
        )

        # 若一帧都没抽出来，尝试 remux 修复容器（-c copy 重写 moov），再抽一次
        if not frame_paths:
            logger.warning("[%s] Frame extraction returned 0 frames (rc=%s); ffmpeg stderr tail: %s",
                           template_id, rc, stderr_text[-500:])
            remuxed_path = os.path.join(tmpdir, "remuxed.mp4")
            async with _get_ffmpeg_semaphore():
                remux_proc = await asyncio.create_subprocess_exec(
                    "ffmpeg", "-y", "-threads", "1", "-fflags", "+genpts",
                    "-probesize", "50M", "-analyzeduration", "100M",
                    "-i", video_path, "-c", "copy", "-movflags", "+faststart", remuxed_path,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                try:
                    _, remux_err = await asyncio.wait_for(remux_proc.communicate(), timeout=60.0)
                except asyncio.TimeoutError:
                    remux_proc.kill()
                    await remux_proc.wait()
                    logger.error("[%s] ffmpeg remux timeout (60s), killed", template_id)
                    remux_err = b"TIMEOUT_KILLED"
            if remux_proc.returncode == 0 and os.path.exists(remuxed_path) and os.path.getsize(remuxed_path) > 0:
                logger.info("[%s] Re-muxed video, retrying frame extraction", template_id)
                rc2, stderr_text2 = await _run_extract(remuxed_path)
                frame_paths = sorted(
                    os.path.join(frames_dir, fn)
                    for fn in os.listdir(frames_dir) if fn.startswith("frame_") and fn.endswith(".jpg")
                )
                if not frame_paths:
                    logger.warning("[%s] Frame extraction still failed after remux (rc=%s); stderr tail: %s",
                                   template_id, rc2, stderr_text2[-500:])
            else:
                logger.warning("[%s] Re-mux failed (rc=%s); stderr tail: %s",
                               template_id, remux_proc.returncode,
                               (remux_err.decode(errors="replace")[-500:] if remux_err else ""))

        if not frame_paths:
            raise RuntimeError(
                f"frame extraction failed: ffmpeg could not decode video "
                f"(file_size={file_size}B, duration={effective_duration:.1f}s). "
                "Check that the video is a real MP4 with a recognizable codec."
            )

        logger.info("[%s] Extracted %d frames via single-pass fps filter", template_id, len(frame_paths))

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

    并发受 _FRAME_UPLOAD_CONCURRENCY 限制，单帧（含 upload_service 内重试）总预算
    _FRAME_UPLOAD_BUDGET_SEC，超时即放弃，由上层 gather 标记为 Exception。
    """
    from app.services.upload_service import UpstreamImageUploadService
    header, b64data = data_url.split(",", 1)
    content = base64.b64decode(b64data)
    svc = UpstreamImageUploadService()
    async with _get_frame_upload_semaphore():
        result = await asyncio.wait_for(
            svc.upload_image(content, "image/jpeg", "frame.jpg"),
            timeout=_FRAME_UPLOAD_BUDGET_SEC,
        )
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

    整个阶段有 _IMAGEGEN_STAGE_TIMEOUT_SEC 的兜底超时，避免 CDN 抖动把 pipeline 永远挂住。
    """
    return await asyncio.wait_for(
        _run_imagegen_stage_inner(template_id=template_id, video_url=video_url),
        timeout=_IMAGEGEN_STAGE_TIMEOUT_SEC,
    )


async def _run_imagegen_stage_inner(
    *,
    template_id: str,
    video_url: str,
) -> list[dict]:
    # 1. 抽帧（1s 间隔）
    frame_data_urls = await _extract_frames_with_interval(video_url, template_id, interval=_FRAME_INTERVAL_NEW)
    if not frame_data_urls:
        raise ValueError("视频抽帧失败，未获取到任何帧图片")

    # 2. 并发上传所有帧到 CDN（受 _FRAME_UPLOAD_CONCURRENCY 限流）
    total = len(frame_data_urls)
    logger.info("[%s] Uploading %d frames to CDN", template_id, total)

    # 进度心跳：每 10s 打一次「已完成 X/N」，避免上传过程中长时间静默看不到进度
    progress = {"done": 0, "failed": 0}

    async def _wrapped_upload(idx: int, du: str):
        try:
            return await _upload_frame_to_cdn(du)
        except Exception as exc:
            progress["failed"] += 1
            return exc
        finally:
            progress["done"] += 1

    async def _heartbeat() -> None:
        import time
        start = time.monotonic()
        try:
            while True:
                await asyncio.sleep(10)
                done = progress["done"]
                logger.info(
                    "[%s] uploading frames: %d/%d done (%d failed), elapsed=%.0fs",
                    template_id, done, total, progress["failed"], time.monotonic() - start,
                )
        except asyncio.CancelledError:
            pass

    heartbeat_task = asyncio.create_task(_heartbeat())
    try:
        upload_results = await asyncio.gather(
            *[_wrapped_upload(i, du) for i, du in enumerate(frame_data_urls)],
            return_exceptions=False,  # 异常已被 _wrapped_upload 捕获并返回
        )
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
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
    "请分析这段视频，判断视频的核心创作意图，"
    "以严格符合 JSON Schema 的结构化数据返回。content_intent 必须从以下四个枚举值中选一："
    "beauty_show（穿搭/美感展示）、knowledge（知识/讲解）、persona_story（人物/故事）、trend_meme（潮流/梗）。\n\n"
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


async def _run_intent_classify_stage(
    *,
    template_id: str,
    video_url: str,
    outfit_details: list[dict],
    model: str,
    prompt: str,
    temperature: float,
) -> dict:
    """意图识别：调用 Gemini，输入视频，要求返回结构化 JSON；
    校验 content_intent，最多 3 次重试。
    （outfit_details 参数保留以兼容调用方，但不再注入 prompt。）
    """
    actual_prompt = prompt.strip() if (prompt and prompt.strip()) else DEFAULT_INTENT_PROMPT

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
    total_products = 0
    total_failed = 0
    for i, detail in enumerate(outfit_details):
        outfit_image_url = detail["image_url"]
        solo_products = detail.get("solo_products", [])

        async def _gen_one(product: dict, outfit_url: str, idx: int) -> str | None:
            # 底层 generate_image 已自带 10 次重试，这里不再叠加业务重试
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
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("[%s] Product image gen outfit[%d] '%s' failed (after lower-level retries): %s",
                             template_id, i, name, exc)
                return None

        tasks = [_gen_one(p, outfit_image_url, i) for p in solo_products]
        img_urls = await asyncio.gather(*tasks)

        outfit_failed = sum(1 for u in img_urls if not u)
        total_products += len(solo_products)
        total_failed += outfit_failed
        if solo_products and outfit_failed == len(solo_products):
            raise ValueError(
                f"product_imagegen outfit[{i}] 所有 {len(solo_products)} 个单品图均生成失败，终止流水线"
            )

        products_with_images = [
            {**p, "product_image_url": url or ""}
            for p, url in zip(solo_products, img_urls)
        ]
        result.append({**detail, "solo_products": products_with_images})
        logger.info("[%s] Product imagegen outfit[%d]: %d/%d 成功", template_id, i,
                    len(solo_products) - outfit_failed, len(solo_products))

    # 整体保护：超过一半单品生图失败也视为流水线失败，避免后续 outfit_regen 拿不到足够素材
    if total_products > 0 and total_failed * 2 > total_products:
        raise ValueError(
            f"product_imagegen 整体失败比例过高（{total_failed}/{total_products}），终止流水线"
        )
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
    failed_outfit_indices: list[int] = []
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

        # 严格模式：拿不到任何单品参考图 → 这套造型直接失败，不再拿抽帧图凑
        if not product_cdn_urls:
            failed_outfit_indices.append(i)
            logger.error(
                "[%s] Outfit regen [%d] FAIL: no product images available (solo_products=%d)",
                template_id, i, len(solo_products),
            )
            continue

        r_prompt = prompt.strip()
        if not r_prompt:
            r_prompt = default_prompt.format(outfit_style=outfit_style)
        else:
            r_prompt = r_prompt.replace("{outfit_style}", outfit_style)

        new_outfit_url: str | None = None
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
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            failed_outfit_indices.append(i)
            logger.error("[%s] Outfit regen [%d] FAIL: generate_image error: %s", template_id, i, exc)
            continue

        final_outfits.append({
            **detail,
            "image_url": new_outfit_url,
            "original_outfit_image_url": outfit_image_url,
        })

    if failed_outfit_indices:
        raise ValueError(
            f"outfit_regen failed for {len(failed_outfit_indices)}/{len(product_gen_results)} outfits "
            f"(indices={failed_outfit_indices})；不再用抽帧图替代，直接终止流水线。"
        )
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

        from app.services.video_task_service import build_prompt_with_image_refs

        for task in tasks:
            if outfit_shots:
                existing = list(task.shots or [])
                if task.has_face and existing:
                    # 保留首位人脸图，其余替换为造型图
                    task.shots = [existing[0], *outfit_shots]
                else:
                    task.shots = outfit_shots
            if prompt_text:
                # 与 create_task 保持一致：按 has_face 与造型图数量拼接 "人物参考/造型参考" 前缀
                task.prompt = build_prompt_with_image_refs(
                    prompt_text,
                    shots_count=len(task.shots or []),
                    has_face=bool(task.has_face),
                )
                task.is_prompt_updated = True
            # AI 模板成功写回，标记本任务已处理完成，一键重试时不再重复触发
            task.ai_retry_done = True

        await session.commit()

    logger.info(
        "[%s] synced prompt/shots to %d tasks (%d outfits, prompt=%s chars)",
        template_id,
        len(tasks),
        len(outfit_shots),
        len(prompt_description or ""),
    )


async def _abandon_linked_tasks_if_marked(template_id: str) -> None:
    """daily-tasks "一键重试" 专用：模板失败时，把对应 video_tasks 标记为 abandoned。

    仅当 batch_restart_templates 通过 abandon_task_ids_on_fail 提前登记过本模板时
    才生效；其他重跑入口不会触发，因此不影响 _run_pipeline 的主流程语义。

    支持两层来源：先看内存（最新一次 batch_restart），再回退到 DB tpl.extra
    （重启后内存丢失但 DB 还保留）。命中后立即清空两边状态，保证幂等。
    """
    task_ids = _abandon_task_ids_on_fail.pop(template_id, None)
    try:
        from sqlalchemy import update as sa_update
        from app.models.video_task import VideoTask
        async with SessionLocal() as session:
            if not task_ids:
                tpl = await session.get(VideoAITemplate, UUID(template_id))
                if tpl and isinstance(tpl.extra, dict):
                    stored = tpl.extra.get("abandon_task_ids_on_fail")
                    if isinstance(stored, list) and stored:
                        task_ids = [str(t) for t in stored]
            if not task_ids:
                return
            await session.execute(
                sa_update(VideoTask)
                .where(VideoTask.id.in_([UUID(t) for t in task_ids]))
                .where(VideoTask.status.notin_(["published", "abandoned"]))
                .values(status="abandoned")
            )
            # 清掉 extra 里的登记，防止下一次重跑误触发
            tpl = await session.get(VideoAITemplate, UUID(template_id))
            if tpl and isinstance(tpl.extra, dict) and (
                "abandon_task_ids_on_fail" in tpl.extra
                or "sync_shots_to_tasks" in tpl.extra
            ):
                cleaned = dict(tpl.extra)
                cleaned.pop("abandon_task_ids_on_fail", None)
                cleaned.pop("sync_shots_to_tasks", None)
                tpl.extra = cleaned
            await session.commit()
        logger.info("[%s] template failed → abandoned %d linked video_tasks", template_id, len(task_ids))
    except Exception as exc:
        logger.error("[%s] failed to abandon linked video_tasks: %s", template_id, exc)


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


# ============================================================================
# 阶段 2.5：8 拼图生成与拆分 + 重洗
# ============================================================================

_LOOKBOOK_GEN_CONCURRENCY = 3   # 单个模板内并发生成 lookbook 数（Gemini 限流）
_PANEL_UPLOAD_CONCURRENCY = 8   # 单 lookbook 内并发上传 8 panel 数


_DEFAULT_LOOKBOOK_ANALYSIS_PROMPT = """你是一名资深时尚造型总监 + prompt 工程师。请把这张参考图分析成一个可复用的"风格系统"，并直接输出一段可以用于图片生成模型的最终 Prompt（8 panel fashion lookbook collage）。重点不是复刻某一套衣服，而是稳定复现同一套"视觉宇宙 + 穿搭语法 + 社媒镜头语言"。

输出要求（必须遵守）：
- 只输出"最终可直接使用的 Prompt 文本"，不要输出分析过程、解释、标题、代码块或 JSON。
- 以"固定层 vs 变化层"的方式组织：固定层保证同风格；变化层制造新鲜感。
- 不要把参考图里最显眼的单一单品（尤其是某条下装）当作系列的固定标准配置；用"轮廓比例 + 镜头语言 + outfit variations"来锁定宇宙。
- 你写的是"元素之间的关系"（色彩对比、廓形对比、镜头语言），而不是单品堆砌。
- 目标是生成"短而强"的可用 Prompt：不要输出长清单式的单品池/语法池/avoid list；用少量高信号词 + 明确 outfit variations 来实现一致性与多样性。
- 色彩不能"降饱和/变保守"：如果参考图存在高饱和或高对比点缀（例如荧光袜/亮色包/强烈格纹），必须在输出中保留其饱和度与对比策略，并在 8 套里多次出现（通过袜/包/内搭/图案点缀等），避免被替换成灰黑驼等低饱和替代品。
- composition 段必须严格使用本模板里给定的版式约束（gutter + 等宽列 + 每格独立构图 + 禁跨界），不要简化、不要省略，便于下游算法等分切割。
- 单人主角硬约束（最重要）：先识别参考图里最主要的时装主角（fashion protagonist，通常是占比最大、构图最聚焦、被造型表达驱动的那一个人）的性别（man / woman / non-binary 等）与基本外观；不要默认女性也不要默认男性。8 个 panel 必须只出现这一位主角，且性别与基本外观（发色发型、肤色、身材比例、年龄段、气质能量）与参考图主角保持一致。参考图里出现的同伴 / 路人 / 群众 / 其他模特，绝不能进入任何一个 panel。即使参考图是机场、街拍、商场、活动等多人场景，也必须把背景重写成只有这位主角一人的环境。

你需要先在脑中完成这些提取（不要在输出里写步骤编号）：
1) 视觉 archetype（社媒风格宇宙）：例如 pinterest girl vibe / tiktok try-on haul / zara lookbook / clean girl 等
2) 轮廓规则（最关键）：用一句话描述上身 vs 下身的比例关系（例如 tiny top + huge bottom / 上部控制下部释放）
3) 社交媒体镜头语言：iphone camera feeling、家居镜子试穿、自然光、构图与姿势能量
4) 变化维度：上装/下装类别轮换、鞋与包的小变化、颜色点缀与图案变化（但人物、场景与镜头语言保持一致）

最终输出格式（严格按此结构输出）：
8 panel fashion lookbook collage, same single subject modeling 8 different outfits, strict single-subject lookbook (only one fashion protagonist appears anywhere across all 8 panels — the same person from panel to panel, with gender and basic appearance matching the reference image's main subject; no companions / no bystanders / no extra people), [一行风格核心：archetype + 情绪 + 时代参考 + 比例规则]

scene:
[用 1-2 行写清楚房间/背景关键物件/氛围。每格独立的同一类场景的不同机位/不同角落，不是把 8 格画成一张连续的房间/街道全景。背景必须是空场（empty of any other human figure）：明确写出 "no other people in frame, no companions, no bystanders, no crowd, no passersby, no partial bodies, no silhouettes or shadows of other people anywhere in the background"。如果参考图本身是机场/街拍/商场/活动等多人场景，请把场景重写成对应风格的同型空场（例如 quiet airport corridor with no other travelers / empty boutique mall corridor / deserted city sidewalk）]

subject:
[被识别为参考图主角的那个人的外观与气质，保持可复现。必须明确写出性别（man / woman / non-binary 等，与参考图一致，不要默认女性也不要默认男性），以及关键特征：发色发型、肤色、身材比例、年龄段、气质能量。明确写 "exactly one human subject is visible in every panel; this is the only person rendered anywhere in the collage; no friend, no partner, no model double, no bystander, no reflection of another person; the subject's gender and basic appearance must match the reference image's main fashion protagonist"]

styling direction:
[一句话写"穿搭语法/轮廓规则/气质能量"]

color palette:
[主色 + 点缀色（5-8 个）；如参考图出现"荧光/高饱和/高对比"颜色，必须明确写入并强调其作为视觉点缀的存在方式]

color strategy:
[一句话说明对比策略与饱和度策略：例如"中性底色 + 高饱和点缀（袜/包/内搭）"或"强烈格纹/印花作为色彩载体"，并要求在 8 套里重复出现点缀色]

outfit variations:
1. [上装] + [下装(类别轮换)] + [鞋] + [配饰/细节]
2. ...
8. ...

accessories:
[配饰方向与一致性锚点]

poses:
[与主角性别气质匹配的镜头语言与姿势能量（不要默认女性化的镜子自拍能量，请根据主角性别与 archetype 选择）。每格内主角必须完整在格内，脚到头都在 panel 边界以内，留有清晰边距，不要紧贴边缘。每格只有一人出现，不要出现第二个人物的手、肩、影子]

composition:
strict 2 rows × 4 columns grid collage of 8 fully independent panels separated by a clean solid white gutter approximately 10–14 px wide both horizontally and vertically, every column has equal width = canvas_width / 4 and every row has equal height = canvas_height / 2, full body framing strictly contained inside each panel with comfortable margin (no body parts, hair, bag straps, leashes, pets, furniture, mirror frames or scene props crossing the gutter into a neighboring panel), each panel is its own independent crop with its own background, camera framing and composition (do NOT render the 8 looks as one continuous room or street scene), consistent overall camera angle and lighting style across panels, vertical social media lookbook format, strict single-subject across the whole collage: exactly one human subject (matching the reference image's main fashion protagonist's gender and core appearance) appears in every panel and no other human figure exists anywhere in any panel (no friend, no partner, no bystander, no passerby, no crowd, no silhouette of another person, no model double)

lighting:
[自然光/真实阴影/手机质感]

style keywords:
[6-10 个关键词，尽量精炼且高信号；从参考图"真实语境"中提取，不要固定套用同一组词]
"""


def _default_lookbook_analysis_prompt() -> str:
    return _DEFAULT_LOOKBOOK_ANALYSIS_PROMPT


def _default_lookbook_imagegen_prompt() -> str:
    """分析输出已经是完整可用的 image-gen prompt（含 composition / 单主角 / 等宽 gutter 等所有约束），
    包装层默认透传，不再叠加冗余指令。
    """
    return "{analysis}"


async def _run_lookbook_stage(
    *,
    template_id: str,
    outfit_shots: list[dict],
    analysis_model: str,
    analysis_prompt: str,
    analysis_temperature: float,
    imagegen_model: str,
    imagegen_prompt: str,
    imagegen_size: str,
    imagegen_quality: str,
) -> list[dict]:
    """对每个 outfit_shot 生成 4×2 lookbook，切割成 8 个 panel 后上传，返回 lookbooks 列表。

    单个 outfit 失败不影响其它（吞异常 + log）；失败的不会出现在返回结果里。
    """
    from app.services.ai_api import call_gemini_api_with_images, generate_image
    from app.utils.image_grid import split_4x2

    actual_analysis_prompt = analysis_prompt.strip() or _default_lookbook_analysis_prompt()
    imagegen_wrapper = imagegen_prompt.strip() or _default_lookbook_imagegen_prompt()

    sem = asyncio.Semaphore(_LOOKBOOK_GEN_CONCURRENCY)
    panel_upload_sem = asyncio.Semaphore(_PANEL_UPLOAD_CONCURRENCY)

    async def _do_one(outfit_index: int, outfit_shot: dict) -> dict:
        """生成单个 outfit 的 lookbook。**任何一步失败都 raise**——
        外层 asyncio.gather + return_exceptions=False 会把异常抛出去，
        最终在 _run_pipeline 的 try/except 翻 status=fail。"""
        outfit_shot_url = outfit_shot.get("image_url")
        if not outfit_shot_url:
            raise ValueError(f"lookbook_gen outfit[{outfit_index}] 缺 image_url")

        async with sem:
            # 1. 分析 Prompt → image-gen prompt
            generated_prompt = await call_gemini_api_with_images(
                model_name=analysis_model,
                prompt=actual_analysis_prompt,
                image_urls=[outfit_shot_url],
                temperature=analysis_temperature,
            )
            generated_prompt = (generated_prompt or "").strip()
            if not generated_prompt:
                raise ValueError(f"lookbook_gen outfit[{outfit_index}] analysis 返回空内容")

            final_prompt = imagegen_wrapper.format(analysis=generated_prompt) \
                if "{analysis}" in imagegen_wrapper else (imagegen_wrapper + "\n\n" + generated_prompt)

            # 2. 生成 4×2 lookbook
            valid_ratios = {"1:1", "1:4", "1:8", "2:3", "3:2", "3:4", "4:1",
                            "4:3", "4:5", "5:4", "8:1", "9:16", "16:9", "21:9"}
            aspect = imagegen_size if imagegen_size in valid_ratios else "4:3"
            if imagegen_size and imagegen_size not in valid_ratios:
                logger.warning(
                    "[%s] lookbook_imagegen_size=%r 不在 Google API 白名单，fallback 4:3",
                    template_id, imagegen_size,
                )
            lookbook_bytes = await generate_image(
                model_name=imagegen_model,
                prompt=final_prompt,
                image_urls=[outfit_shot_url],   # 传 outfit_shot 做参考图保证主角一致
                aspect_ratio=aspect,
                image_size=imagegen_quality or "2K",
            )

            # 3. 上传整张 lookbook
            lookbook_url = await _upload_image_bytes(
                lookbook_bytes,
                filename=f"lookbook_{template_id[:8]}_outfit{outfit_index}.png",
            )

            # 4. 切割成 8 panel
            panel_bytes_list = await asyncio.to_thread(split_4x2, lookbook_bytes)
            if len(panel_bytes_list) != 8:
                raise ValueError(
                    f"lookbook_gen outfit[{outfit_index}] 切割结果非 8（{len(panel_bytes_list)}）"
                )

            # 5. 并发上传 8 panel —— 任何一个失败也算整个 outfit 失败
            async def _upload_panel(idx_zero_based: int) -> str:
                async with panel_upload_sem:
                    return await _upload_image_bytes(
                        panel_bytes_list[idx_zero_based],
                        filename=f"lookbook_{template_id[:8]}_o{outfit_index}_p{idx_zero_based + 1}.png",
                    )

            panel_urls = await asyncio.gather(*[_upload_panel(i) for i in range(8)])

            return {
                "outfit_index": outfit_index,
                "outfit_shot_image_url": outfit_shot_url,
                "generated_prompt": generated_prompt,
                "lookbook_image_url": lookbook_url,
                "panels": [
                    {
                        "index": i + 1,
                        "image_url": panel_urls[i],
                        "is_reference": (i == 0),  # panel_1 留作参考图
                        "used_in_remix_id": None,
                    }
                    for i in range(8)
                ],
                "regenerated_count": 0,
                "last_regenerated_at": None,
            }

    # 任一 outfit 失败就抛出（match _run_outfit_detail_analysis 的严格语义）
    results = await asyncio.gather(
        *[_do_one(i, o) for i, o in enumerate(outfit_shots)],
        return_exceptions=True,
    )
    failures = [(i, r) for i, r in enumerate(results) if isinstance(r, Exception)]
    if failures:
        idx, exc = failures[0]
        logger.error(
            "[%s] lookbook_gen 整体失败：共 %d 个 outfit，其中 %d 个失败；首个错误 outfit[%d]: %s",
            template_id, len(results), len(failures), idx, exc,
        )
        raise ValueError(
            f"lookbook_gen 失败 {len(failures)}/{len(results)} 个 outfit；"
            f"first error at outfit[{idx}]: {exc}"
        ) from exc
    return list(results)


async def _upload_image_bytes(image_bytes: bytes, *, filename: str) -> str:
    """走现有 CDN 上传通道，返回 url。"""
    from app.services.upload_service import UpstreamImageUploadService, detect_image_content_type
    content_type, _ext = detect_image_content_type(image_bytes)
    svc = UpstreamImageUploadService()
    result = await svc.upload_image(image_bytes, content_type, filename)
    return result.url


async def _ensure_each_outfit_has_unused_panel(
    template_id: str, lookbooks: list[dict],
) -> list[dict]:
    """对每个 lookbook：panel_2~8 全部已用时自动重生成（用户不感知）。
    返回更新后的 lookbooks（保持顺序）；内部调 _regenerate_outfit_lookbook 会写 DB。
    """
    updated = list(lookbooks)
    regen_count = 0
    for i, lb in enumerate(updated):
        panels = lb.get("panels") or []
        has_unused = any(
            not p.get("is_reference") and not p.get("used_in_remix_id")
            for p in panels
        )
        if has_unused:
            continue
        oi = lb.get("outfit_index")
        logger.info(
            "[%s] outfit[%s] lookbook 池子耗尽，自动重生成 8 拼图",
            template_id, oi,
        )
        new_lookbooks = await _regenerate_outfit_lookbook(
            template_id=template_id,
            outfit_index=oi,
        )
        for new_lb in new_lookbooks:
            if new_lb.get("outfit_index") == oi:
                updated[i] = new_lb
                break
        regen_count += 1
    if regen_count > 0:
        logger.info("[%s] 自动重生 %d 个 lookbook 完成", template_id, regen_count)
    return updated


def _auto_pick_initial_panels_for_lookbooks(lookbooks: list[dict]) -> tuple[list[dict], list[dict]]:
    """给每个 lookbook 选一个未用、非参考的 panel，标记为 used，并返回拾起信息。

    返回 (lookbooks 原对象被原地修改, picked_entries)
    picked_entries 每条形如 {remix_id, outfit_index, panel_index, panel_image_url}。
    若某 lookbook 池子已全用完，跳过该 lookbook（这种情况只在断点续跑或异常时出现）。
    """
    picked: list[dict] = []
    for lb in lookbooks:
        target = None
        for p in lb["panels"]:
            if p.get("is_reference"):
                continue
            if p.get("used_in_remix_id"):
                continue
            target = p
            break
        if target is None:
            continue
        remix_id = str(uuid4())
        target["used_in_remix_id"] = remix_id
        picked.append({
            "remix_id": remix_id,
            "outfit_index": lb["outfit_index"],
            "panel_index": target["index"],
            "panel_image_url": target["image_url"],
        })
    return lookbooks, picked


async def _finalize_initial_remixes(
    template_id: str,
    *,
    success: bool,
    error_message: str | None = None,
) -> None:
    """pipeline 结束时（success / fail），把本次 auto-initial remix_history 行 status 翻成最终状态。

    成功时 downstream_result 用 state 里的 final_outfits / extracted_shots 摘录。
    """
    state = video_ai_states.get(template_id) or {}
    initial_remix_ids = state.get("initial_remix_ids") or []
    if not initial_remix_ids:
        return
    final_outfits = state.get("final_outfits") or []
    extracted_shots = state.get("extracted_shots") or []
    now_iso = _utcnow_iso()
    async with SessionLocal() as session:
        tpl = await session.get(VideoAITemplate, UUID(template_id))
        if tpl is None:
            return
        history = list(tpl.remix_history or [])
        for h in history:
            if h.get("remix_id") in initial_remix_ids and h.get("status") == "running":
                h["completed_at"] = now_iso
                if success:
                    h["status"] = "success"
                    # 用 outfit_index 找对应位置的最终造型图
                    oi = h.get("outfit_index")
                    matched = final_outfits[oi] if isinstance(oi, int) and 0 <= oi < len(final_outfits) else None
                    h["downstream_result"] = {
                        "final_outfit": matched,
                        "extracted_shot": extracted_shots[oi] if isinstance(oi, int) and 0 <= oi < len(extracted_shots) else None,
                    }
                else:
                    h["status"] = "failed"
                    h["error_message"] = (error_message or "")[:500]
        tpl.remix_history = history
        await session.commit()
    # 同步清掉 state.initial_remix_ids 防止下次断点续跑误判（视为完成）
    if state:
        state.pop("initial_remix_ids", None)


# ----- Soft retry：从阶段 2.5 重新挑 panel + 跑下游（不重抽帧/不重识别穿搭/不重生 lookbook） -----


async def soft_retry_template(
    template_id: str,
    *,
    abandon_task_ids_on_fail: list[str] | None = None,
    cta: bool | None = None,
) -> None:
    """从阶段 2.5 软重试：复用已有 lookbooks，给每个 outfit 重新挑下一个未用 panel + 跑下游。

    跟 hard restart 区别：
      - 不重跑 imagegen / outfit_selecting / lookbook_gen（这些 stages 标记为 completed）
      - state.initial_remix_ids 和 outfit_shots 被清空，让 _run_pipeline 重新自动挑 panel
      - 已使用过的 panel 保留 used_in_remix_id 标记，不会被重复挑
      - **某 outfit 池子耗尽 → pipeline 内自动重生该 outfit 的 lookbook（用户不感知）**

    若模板压根没有 lookbooks（老模板）→ raise ValueError，调用方应回退到 hard restart。
    """
    async with SessionLocal() as session:
        tpl = await session.get(VideoAITemplate, UUID(template_id))
        if tpl is None:
            raise ValueError(f"template {template_id} 不存在")
        if not tpl.lookbooks:
            # 完全没有 lookbook（老模板）→ 上层应该 fallback 到 hard restart
            raise ValueError(f"template {template_id} 还没有 lookbook，无法 soft retry")
        # 池子耗尽不报错；pipeline 会自动重生 lookbook（用户不感知）

        # 解析现有 state，清掉本次要重做的部分
        state: dict = {}
        if tpl.process_state:
            try:
                state = json.loads(tpl.process_state) or {}
            except Exception:
                state = {}
        # 保留 imagegen/outfit_selecting/lookbook_gen 已完成的标记，去掉下游
        completed = list(state.get("completed_stages") or [])
        preserve = {"imagegen", "outfit_selecting", "lookbook_gen"}
        state["completed_stages"] = [s for s in completed if s in preserve]
        # 确保三个上游阶段都标记完成（万一历史 state 缺）
        for s in ("imagegen", "outfit_selecting", "lookbook_gen"):
            if s not in state["completed_stages"]:
                state["completed_stages"].append(s)
        # 关键：清掉 initial_remix_ids 让 pipeline 重新挑 panel；清掉 outfit_shots 让 pipeline 用 panel 替代
        state.pop("initial_remix_ids", None)
        state.pop("outfit_shots", None)
        # 清掉下游产物
        for k in ("outfit_detailing_progress", "intent_json", "prompt_description",
                  "product_gen_results", "product_search_results", "final_outfits", "extracted_shots"):
            state.pop(k, None)
        state["status"] = VideoAIProcessStatus.pending.value
        state["error_message"] = ""
        state["updated_at"] = _utcnow_iso()

        # extra 字段也清掉对应中间产物
        extra = dict(tpl.extra or {})
        for k in ("outfit_detailing_progress", "intent_json", "product_gen_results",
                  "product_search_results", "final_outfits"):
            extra.pop(k, None)
        # cta / abandon map 通过 extra 透传给 _run_pipeline（与 batch_restart 同款 protocol）
        if abandon_task_ids_on_fail is not None:
            extra["abandon_task_ids_on_fail"] = list(abandon_task_ids_on_fail)
        # 关键：标记成功结束时把 final_outfits 同步回关联 video_tasks（同 hard restart）
        extra["sync_shots_to_tasks"] = True
        if cta is not None:
            state["cta"] = bool(cta)

        tpl.process_state = json.dumps(state, ensure_ascii=False)
        tpl.process_status = VideoAIProcessStatus.pending
        tpl.process_error = None
        tpl.extracted_shots = None
        tpl.extra = extra
        await session.commit()

    # 内存 state 同步刷新（state 已是 dict 形式，无需额外 normalize）
    video_ai_states[template_id] = state
    _mark_dirty(template_id)
    _sync_shots_on_success.add(template_id)
    if abandon_task_ids_on_fail is not None:
        _abandon_task_ids_on_fail[template_id] = list(abandon_task_ids_on_fail)

    # 入队
    await enqueue_template(template_id)
    logger.info("[%s] soft retry 已入队（从阶段 2.5 重挑 panel + 跑下游）", template_id)


async def batch_soft_retry_templates(
    *,
    template_ids: list[str],
    abandon_task_ids_on_fail: dict[str, list[str]] | None = None,
    cta_map: dict[str, bool] | None = None,
) -> dict:
    """批量 soft retry。对每个模板：若有 lookbook 且至少一个 outfit 池子还有未用 panel 就 soft；
    否则 fallback 到 hard restart。

    返回 {soft: [...], hard_fallback: [...], skipped: [...]}（id 列表）
    """
    soft_ids: list[str] = []
    hard_fallback_ids: list[str] = []
    skipped: list[str] = []
    for tpl_id in template_ids:
        try:
            await soft_retry_template(
                tpl_id,
                abandon_task_ids_on_fail=(abandon_task_ids_on_fail or {}).get(tpl_id),
                cta=(cta_map or {}).get(tpl_id),
            )
            soft_ids.append(tpl_id)
        except ValueError as exc:
            # 没有 lookbook 或池子全耗尽 → 走 hard restart 兜底
            logger.info("[%s] soft retry 不可用，fallback hard restart: %s", tpl_id, exc)
            try:
                await batch_restart_templates(
                    owner_id=None,
                    template_ids=[tpl_id],
                    abandon_task_ids_on_fail={tpl_id: (abandon_task_ids_on_fail or {}).get(tpl_id, [])} if abandon_task_ids_on_fail else None,
                    cta_map={tpl_id: (cta_map or {}).get(tpl_id, False)} if cta_map else None,
                )
                hard_fallback_ids.append(tpl_id)
            except Exception as exc2:
                logger.exception("[%s] hard restart 兜底也失败: %s", tpl_id, exc2)
                skipped.append(tpl_id)
        except Exception as exc:
            logger.exception("[%s] soft retry 异常: %s", tpl_id, exc)
            skipped.append(tpl_id)
    logger.info(
        "batch_soft_retry_templates 完成：soft=%d hard_fallback=%d skipped=%d",
        len(soft_ids), len(hard_fallback_ids), len(skipped),
    )
    return {"soft": soft_ids, "hard_fallback": hard_fallback_ids, "skipped": skipped}


# ----- Remix 触发 -----

# 进程内锁：避免同一 template 并发 remix 时抢同一 panel
_remix_locks: dict[str, asyncio.Lock] = {}


def _get_remix_lock(template_id: str) -> asyncio.Lock:
    lock = _remix_locks.get(template_id)
    if lock is None:
        lock = asyncio.Lock()
        _remix_locks[template_id] = lock
    return lock


async def remix_template(
    template_id: str,
    *,
    outfit_index: int | None = None,
    panel_index: int | None = None,
) -> dict:
    """触发一次重洗。

    1. 选 panel（指定/round-robin/池子耗尽时重生 lookbook）
    2. 写 remix_history 一行（status=running）+ 标记 panel.used_in_remix_id + remix_count+=1
    3. asyncio.create_task 后台跑下游 stages
    4. 立即返回 {remix_id, outfit_index, panel_index, panel_image_url, status="running"}
    """
    from app.models.video_ai_template import VideoAITemplate

    async with _get_remix_lock(template_id):
        async with SessionLocal() as session:
            tpl = await session.get(VideoAITemplate, UUID(template_id))
            if tpl is None:
                raise ValueError(f"template {template_id} 不存在")
            if not tpl.lookbooks:
                raise ValueError("该模板还没有 lookbook（阶段 2.5 未完成）")

            lookbooks: list[dict] = list(tpl.lookbooks or [])
            target_outfit, target_panel = _pick_panel_for_remix(lookbooks, outfit_index, panel_index)

            if target_panel is None:
                # 池子耗尽 → 重新生成该 outfit 的 lookbook
                outfit_for_regen = target_outfit if target_outfit is not None else 0
                logger.info("[%s] remix: outfit[%d] 池子耗尽，重新生成 lookbook", template_id, outfit_for_regen)
                lookbooks = await _regenerate_outfit_lookbook(
                    template_id=template_id, outfit_index=outfit_for_regen,
                )
                tpl.lookbooks = lookbooks
                await session.commit()
                target_outfit, target_panel = _pick_panel_for_remix(lookbooks, outfit_for_regen, None)
                if target_panel is None:
                    raise RuntimeError("lookbook 重生后仍无可用 panel（生成失败）")

            remix_id = uuid4()
            now = _utcnow_iso()

            # 标记 panel.used_in_remix_id
            for lb in lookbooks:
                if lb["outfit_index"] == target_outfit:
                    for p in lb["panels"]:
                        if p["index"] == target_panel["index"]:
                            p["used_in_remix_id"] = str(remix_id)
                            break
                    break

            # remix_history 追加
            history = list(tpl.remix_history or [])
            history.append({
                "remix_id": str(remix_id),
                "outfit_index": target_outfit,
                "panel_index": target_panel["index"],
                "panel_image_url": target_panel["image_url"],
                "started_at": now,
                "completed_at": None,
                "status": "running",
                "error_message": None,
                "downstream_result": None,
            })

            tpl.lookbooks = lookbooks
            tpl.remix_history = history
            tpl.remix_count = (tpl.remix_count or 0) + 1
            await session.commit()

    # 异步触发下游
    asyncio.create_task(_run_downstream_for_remix(
        template_id=template_id,
        remix_id=str(remix_id),
        outfit_index=target_outfit,
        panel=target_panel,
    ))

    return {
        "remix_id": remix_id,
        "outfit_index": target_outfit,
        "panel_index": target_panel["index"],
        "panel_image_url": target_panel["image_url"],
        "status": "running",
    }


def _pick_panel_for_remix(
    lookbooks: list[dict],
    requested_outfit: int | None,
    requested_panel: int | None,
) -> tuple[int | None, dict | None]:
    """从 lookbooks 里挑下一个未用 panel。

    - 指定 outfit + panel → 必须精确匹配且未用
    - 仅指定 outfit → 该 outfit 池子里下一个 is_reference=False 且 used_in_remix_id=None
    - 都不指定 → 跨 outfit round-robin（先用 outfit_0 panel_2，再 outfit_1 panel_2，依次...）

    返回 (outfit_index, panel_dict)；选不到时 panel=None。
    """
    if not lookbooks:
        return None, None

    if requested_outfit is not None and requested_panel is not None:
        for lb in lookbooks:
            if lb["outfit_index"] != requested_outfit:
                continue
            for p in lb["panels"]:
                if p["index"] == requested_panel:
                    if p.get("is_reference"):
                        return requested_outfit, None
                    if p.get("used_in_remix_id"):
                        return requested_outfit, None
                    return requested_outfit, p
            return requested_outfit, None
        return requested_outfit, None

    if requested_outfit is not None:
        for lb in lookbooks:
            if lb["outfit_index"] != requested_outfit:
                continue
            for p in lb["panels"]:
                if p.get("is_reference"):
                    continue
                if p.get("used_in_remix_id"):
                    continue
                return requested_outfit, p
        return requested_outfit, None

    # round-robin：按 panel_index 优先，遍历 panels[2..8] × outfits
    max_panels = max((len(lb["panels"]) for lb in lookbooks), default=0)
    for panel_i in range(2, max_panels + 1):
        for lb in lookbooks:
            for p in lb["panels"]:
                if p["index"] != panel_i:
                    continue
                if p.get("is_reference") or p.get("used_in_remix_id"):
                    continue
                return lb["outfit_index"], p
    return None, None


async def _regenerate_outfit_lookbook(*, template_id: str, outfit_index: int) -> list[dict]:
    """重生某 outfit 的 lookbook（panels 池子重置）。返回更新后的 lookbooks 列表。"""
    from app.models.video_ai_template import VideoAITemplate

    async with SessionLocal() as session:
        tpl = await session.get(VideoAITemplate, UUID(template_id))
        if tpl is None:
            raise ValueError(f"template {template_id} 不存在")
        lookbooks = list(tpl.lookbooks or [])
        target = next((lb for lb in lookbooks if lb["outfit_index"] == outfit_index), None)
        if target is None:
            raise ValueError(f"outfit_index={outfit_index} 不存在")

        cfg = await _load_pipeline_settings_for_template(session, tpl)

    # 用原来的 outfit_shot_image_url 当 reference 重新走一遍 _run_lookbook_stage 的单条逻辑
    single = await _run_lookbook_stage(
        template_id=template_id,
        outfit_shots=[{
            "image_url": target["outfit_shot_image_url"],
            "frame_index": None,
            "group_frame_indices": [],
        }],
        analysis_model=cfg["lookbook_analysis_model"],
        analysis_prompt=cfg["lookbook_analysis_prompt"],
        analysis_temperature=cfg["lookbook_analysis_temperature"],
        imagegen_model=cfg["lookbook_imagegen_model"],
        imagegen_prompt=cfg["lookbook_imagegen_prompt"],
        imagegen_size=cfg["lookbook_imagegen_size"],
        imagegen_quality=cfg["lookbook_imagegen_quality"],
    )
    if not single:
        raise RuntimeError("lookbook 重生失败")

    new_lb = single[0]
    new_lb["outfit_index"] = outfit_index
    new_lb["regenerated_count"] = (target.get("regenerated_count") or 0) + 1
    new_lb["last_regenerated_at"] = _utcnow_iso()

    async with SessionLocal() as session:
        tpl = await session.get(VideoAITemplate, UUID(template_id))
        lookbooks = list(tpl.lookbooks or [])
        for i, lb in enumerate(lookbooks):
            if lb["outfit_index"] == outfit_index:
                lookbooks[i] = new_lb
                break
        tpl.lookbooks = lookbooks
        await session.commit()
    return lookbooks


async def _load_pipeline_settings_for_template(session: AsyncSession, tpl) -> dict:
    from app.services.pipeline_settings_service import get_or_create_pipeline_settings
    cfg_owner = tpl.owner_id if tpl.owner_id is not None else UUID(int=0)
    ps = await get_or_create_pipeline_settings(session, owner_id=cfg_owner)
    return {
        "lookbook_analysis_model": ps.lookbook_analysis_model,
        "lookbook_analysis_prompt": ps.lookbook_analysis_prompt,
        "lookbook_analysis_temperature": ps.lookbook_analysis_temperature,
        "lookbook_imagegen_model": ps.lookbook_imagegen_model,
        "lookbook_imagegen_prompt": ps.lookbook_imagegen_prompt,
        "lookbook_imagegen_size": ps.lookbook_imagegen_size,
        "lookbook_imagegen_quality": ps.lookbook_imagegen_quality,
    }


async def _run_downstream_for_remix(
    *,
    template_id: str,
    remix_id: str,
    outfit_index: int,
    panel: dict,
) -> None:
    """后台跑 outfit_detailing → product_imagegen → outfit_regen，对选中的 panel 当 outfit reference。

    完成后写回 remix_history 那一行的 status / completed_at / downstream_result。
    """
    from app.models.video_ai_template import VideoAITemplate

    panel_url = panel["image_url"]
    panel_idx = panel["index"]
    single_outfit_shot = [{
        "image_url": panel_url,
        "frame_index": None,
        "group_frame_indices": [],
    }]

    error_msg: str | None = None
    downstream_result: dict | None = None

    try:
        # 取 pipeline settings
        async with SessionLocal() as session:
            tpl = await session.get(VideoAITemplate, UUID(template_id))
            if tpl is None:
                raise ValueError(f"template {template_id} 不存在")
            from app.services.pipeline_settings_service import get_or_create_pipeline_settings
            cfg_owner = tpl.owner_id if tpl.owner_id is not None else UUID(int=0)
            ps = await get_or_create_pipeline_settings(session, owner_id=cfg_owner)
            outfit_detail_model = ps.outfit_detail_model
            outfit_detail_prompt = ps.outfit_detail_prompt
            outfit_detail_temperature = ps.outfit_detail_temperature
            product_imagegen_model = ps.product_imagegen_model
            product_imagegen_prompt = ps.product_imagegen_prompt
            product_imagegen_size = ps.product_imagegen_size
            product_imagegen_quality = ps.product_imagegen_quality
            outfit_regen_model = ps.outfit_regen_model
            outfit_regen_prompt = ps.outfit_regen_prompt
            outfit_regen_size = ps.outfit_regen_size
            outfit_regen_quality = ps.outfit_regen_quality

        _set_status(template_id, VideoAIProcessStatus.remixing)

        # 1. 单 outfit 单品理解
        outfit_details = await _run_outfit_detail_analysis(
            template_id=template_id,
            outfit_shots=single_outfit_shot,
            model=outfit_detail_model,
            prompt=outfit_detail_prompt,
            temperature=outfit_detail_temperature,
        )

        # 2. 单品生图
        product_gen_results = await _run_product_imagegen(
            template_id=template_id,
            outfit_details=outfit_details,
            outfit_shots=single_outfit_shot,
            model=product_imagegen_model,
            prompt=product_imagegen_prompt,
            size=product_imagegen_size,
            quality=product_imagegen_quality,
        )

        # 3. 新造型生图
        final_outfits = await _run_outfit_regen(
            template_id=template_id,
            outfit_details=outfit_details,
            product_gen_results=product_gen_results,
            outfit_shots=single_outfit_shot,
            model=outfit_regen_model,
            prompt=outfit_regen_prompt,
            size=outfit_regen_size,
            quality=outfit_regen_quality,
        )

        downstream_result = {
            "outfit_details": outfit_details,
            "product_gen_results": product_gen_results,
            "final_outfits": final_outfits,
        }
        logger.info("[%s] remix %s downstream 完成 (outfit_idx=%d panel_idx=%d)",
                    template_id, remix_id, outfit_index, panel_idx)
    except Exception as exc:
        logger.exception("[%s] remix %s downstream 失败: %s", template_id, remix_id, exc)
        error_msg = str(exc)[:500]

    # 写回 remix_history 这一行
    async with SessionLocal() as session:
        tpl = await session.get(VideoAITemplate, UUID(template_id))
        if tpl is None:
            return
        history = list(tpl.remix_history or [])
        for h in history:
            if h["remix_id"] == remix_id:
                h["completed_at"] = _utcnow_iso()
                h["status"] = "success" if error_msg is None else "failed"
                h["error_message"] = error_msg
                h["downstream_result"] = downstream_result
                break
        tpl.remix_history = history
        await session.commit()
    _set_status(template_id, VideoAIProcessStatus.success)
    await _persist_states([template_id])


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

                        # 优先 local_video_url（CDN）→ 回退 local_gcs_video_url（GCS）→ 最后原始 video_url
                        if vs.local_video_url:
                            video_url = vs.local_video_url
                            logger.info("[%s] Using local_video_url (CDN): %s", template_id, video_url[:100] + "...")
                        elif vs.local_gcs_video_url:
                            video_url = vs.local_gcs_video_url
                            logger.info("[%s] Using local_gcs_video_url (GCS): %s", template_id, video_url[:100] + "...")
                        elif vs.video_url:
                            video_url = vs.video_url
                            logger.warning("[%s] Using original video_url (platform) - may not work with Gemini: %s", template_id, video_url[:100] + "...")

                if not video_url:
                    logger.warning("[%s] No video URL available", template_id)
                    _set_status(template_id, VideoAIProcessStatus.fail, error="视频地址不可用")
                    await _persist_states([template_id])
                    return

                # 加载用户流程配置（admin 也有 owner_id，按 owner_id 直接读）
                from app.services.pipeline_settings_service import get_or_create_pipeline_settings
                logger.info("[%s] loading pipeline_settings for owner_id=%s", template_id, tpl.owner_id)
                if tpl.owner_id is not None:
                    pipeline_cfg = await get_or_create_pipeline_settings(session, owner_id=tpl.owner_id)
                    # 是否走「有CTA」一套提示词；为空则回落到对应的非 CTA 提示词
                    cta_flag = bool((video_ai_states.get(template_id) or {}).get("cta"))

                    def _pick(non_cta_value: str, cta_value: str) -> str:
                        if cta_flag and (cta_value or "").strip():
                            return cta_value
                        return non_cta_value or ""

                    # 视频理解（在 outfit_detailing 之后，按 content_intent 分支）
                    understand_model = pipeline_cfg.understand_model or "gemini-3.1-pro-preview"
                    understand_temperature = pipeline_cfg.understand_temperature
                    understand_prompts_by_intent = {
                        "beauty_show": _pick(pipeline_cfg.understand_prompt_beauty_show, pipeline_cfg.understand_prompt_beauty_show_cta),
                        "knowledge": _pick(pipeline_cfg.understand_prompt_knowledge, pipeline_cfg.understand_prompt_knowledge_cta),
                        "persona_story": _pick(pipeline_cfg.understand_prompt_persona_story, pipeline_cfg.understand_prompt_persona_story_cta),
                        "trend_meme": _pick(pipeline_cfg.understand_prompt_trend_meme, pipeline_cfg.understand_prompt_trend_meme_cta),
                    }
                    # 意图识别
                    intent_classify_model = pipeline_cfg.intent_classify_model or "gemini-3.1-pro-preview"
                    intent_classify_prompt = _pick(pipeline_cfg.intent_classify_prompt, pipeline_cfg.intent_classify_prompt_cta)
                    intent_classify_temperature = pipeline_cfg.intent_classify_temperature
                    # 穿搭识别
                    outfit_select_model = pipeline_cfg.outfit_select_model or "gemini-3.1-pro-preview"
                    outfit_select_prompt = _pick(pipeline_cfg.outfit_select_prompt, pipeline_cfg.outfit_select_prompt_cta)
                    outfit_select_temperature = pipeline_cfg.outfit_select_temperature
                    # 穿搭单品理解
                    outfit_detail_model = pipeline_cfg.outfit_detail_model or "gemini-3.1-pro-preview"
                    outfit_detail_prompt = _pick(pipeline_cfg.outfit_detail_prompt, pipeline_cfg.outfit_detail_prompt_cta)
                    outfit_detail_temperature = pipeline_cfg.outfit_detail_temperature
                    # 单品图生成
                    product_imagegen_model = pipeline_cfg.product_imagegen_model or "gemini-3.1-flash-image-preview"
                    product_imagegen_prompt = _pick(pipeline_cfg.product_imagegen_prompt, pipeline_cfg.product_imagegen_prompt_cta)
                    product_imagegen_size = pipeline_cfg.product_imagegen_size or "1:1"
                    product_imagegen_quality = pipeline_cfg.product_imagegen_quality or "2K"
                    # 新造型图生成
                    outfit_regen_model = pipeline_cfg.outfit_regen_model or "gemini-3.1-flash-image-preview"
                    outfit_regen_prompt = _pick(pipeline_cfg.outfit_regen_prompt, pipeline_cfg.outfit_regen_prompt_cta)
                    outfit_regen_size = pipeline_cfg.outfit_regen_size or "9:16"
                    outfit_regen_quality = pipeline_cfg.outfit_regen_quality or "2K"
                    logger.info("[%s] cta=%s, prompts loaded.", template_id, cta_flag)

                    # 调试：打印从 pipeline_settings 读到的 prompt 文案（空 = 走代码默认）
                    logger.info(
                        "[%s] pipeline_settings prompts (owner=%s):\n"
                        "  outfit_select_prompt (%d chars): %s\n"
                        "  outfit_detail_prompt (%d chars): %s\n"
                        "  intent_classify_prompt (%d chars): %s\n"
                        "  understand_prompt_beauty_show (%d chars): %s\n"
                        "  understand_prompt_knowledge (%d chars): %s\n"
                        "  understand_prompt_persona_story (%d chars): %s\n"
                        "  understand_prompt_trend_meme (%d chars): %s\n"
                        "  product_imagegen_prompt (%d chars): %s\n"
                        "  outfit_regen_prompt (%d chars): %s",
                        template_id, tpl.owner_id,
                        len(outfit_select_prompt), outfit_select_prompt or "<empty → default>",
                        len(outfit_detail_prompt), outfit_detail_prompt or "<empty → default>",
                        len(intent_classify_prompt), intent_classify_prompt or "<empty → default>",
                        len(understand_prompts_by_intent["beauty_show"]),
                        understand_prompts_by_intent["beauty_show"] or "<empty → default>",
                        len(understand_prompts_by_intent["knowledge"]),
                        understand_prompts_by_intent["knowledge"] or "<empty → default>",
                        len(understand_prompts_by_intent["persona_story"]),
                        understand_prompts_by_intent["persona_story"] or "<empty → default>",
                        len(understand_prompts_by_intent["trend_meme"]),
                        understand_prompts_by_intent["trend_meme"] or "<empty → default>",
                        len(product_imagegen_prompt), product_imagegen_prompt or "<empty → default>",
                        len(outfit_regen_prompt), outfit_regen_prompt or "<empty → default>",
                    )
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

            # ========== 步骤 2.5: 8 拼图生成与拆分（每个 outfit_shot → 4×2 lookbook → 8 panel）==========
            if "lookbook_gen" in completed_stages:
                # 断点续跑 / soft retry：从 DB 读现成 lookbooks，跳过生成
                async with SessionLocal() as session:
                    _tpl_for_lb = await session.get(VideoAITemplate, uuid_val)
                    lookbooks = list(_tpl_for_lb.lookbooks or []) if _tpl_for_lb else []
                state["lookbooks"] = lookbooks
                logger.info("[%s] lookbook_gen skipped (already completed), %d lookbooks restored", template_id, len(lookbooks))
            else:
                _set_status(template_id, VideoAIProcessStatus.lookbook_gen)
                logger.info("[%s] lookbook_gen stage started, %d outfit_shots", template_id, len(outfit_shots))
                try:
                    lookbooks = await _run_lookbook_stage(
                        template_id=template_id,
                        outfit_shots=outfit_shots,
                        analysis_model=pipeline_cfg.lookbook_analysis_model,
                        analysis_prompt=pipeline_cfg.lookbook_analysis_prompt,
                        analysis_temperature=pipeline_cfg.lookbook_analysis_temperature,
                        imagegen_model=pipeline_cfg.lookbook_imagegen_model,
                        imagegen_prompt=pipeline_cfg.lookbook_imagegen_prompt,
                        imagegen_size=pipeline_cfg.lookbook_imagegen_size,
                        imagegen_quality=pipeline_cfg.lookbook_imagegen_quality,
                    )
                except Exception as exc:
                    logger.exception("[%s] lookbook_gen stage failed: %s", template_id, exc)
                    raise
                state["lookbooks"] = lookbooks
                state["updated_at"] = _utcnow_iso()
                if "lookbook_gen" not in state.get("completed_stages", []):
                    state.setdefault("completed_stages", []).append("lookbook_gen")
                _mark_dirty(template_id)
                async with SessionLocal() as session:
                    tpl = await session.get(VideoAITemplate, uuid_val)
                    if tpl:
                        tpl.lookbooks = lookbooks
                        tpl.process_state = json.dumps(state, ensure_ascii=False)
                        await session.commit()
                logger.info(
                    "[%s] lookbook_gen completed, %d lookbooks (each w/ 7-panel pool)",
                    template_id, len(lookbooks),
                )

            # ========== 阶段 2.5 完成后：自动给每个 outfit 挑一个未用 panel 作为下游 outfit reference ==========
            # 若已经有 auto-initial 标记的 remix（如断点续跑场景），就不重复挑；否则挑 panel_2~8 中第一个未用。
            # 任一 outfit 池子耗尽 → 透明地自动重生 lookbook（用户不感知）
            initial_remix_ids: list[str] = state.get("initial_remix_ids") or []
            if not initial_remix_ids and lookbooks:
                lookbooks = await _ensure_each_outfit_has_unused_panel(template_id, lookbooks)
                state["lookbooks"] = lookbooks
                _, picked = _auto_pick_initial_panels_for_lookbooks(lookbooks)
                if not picked:
                    # 兜底：重生成后仍挑不到（生成失败的极少数情况）
                    logger.error("[%s] 自动重生 lookbook 后仍无可用 panel，pipeline 失败", template_id)
                    raise RuntimeError("阶段 2.5 重生 lookbook 后仍无可用 panel")
                else:
                    panel_outfit_shots: list[dict] = []
                    history = list(state.get("remix_history") or [])
                    now_iso = _utcnow_iso()
                    for entry in picked:
                        initial_remix_ids.append(entry["remix_id"])
                        history.append({
                            "remix_id": entry["remix_id"],
                            "outfit_index": entry["outfit_index"],
                            "panel_index": entry["panel_index"],
                            "panel_image_url": entry["panel_image_url"],
                            "started_at": now_iso,
                            "completed_at": None,
                            "status": "running",
                            "error_message": None,
                            "downstream_result": None,
                            "is_initial": True,
                        })
                        panel_outfit_shots.append({
                            "image_url": entry["panel_image_url"],
                            "frame_index": None,
                            "group_frame_indices": [],
                        })
                    state["initial_remix_ids"] = initial_remix_ids
                    state["remix_history"] = history
                    # 用 panel 替换 outfit_shots 喂给下游（不破坏 stage 2 的原数据，原数据在 lookbooks[].outfit_shot_image_url 里）
                    outfit_shots = panel_outfit_shots
                    state["outfit_shots"] = panel_outfit_shots
                    async with SessionLocal() as session:
                        tpl = await session.get(VideoAITemplate, uuid_val)
                        if tpl:
                            tpl.lookbooks = lookbooks
                            tpl.remix_history = history
                            tpl.remix_count = (tpl.remix_count or 0) + len(picked)
                            tpl.process_state = json.dumps(state, ensure_ascii=False)
                            await session.commit()
                    logger.info(
                        "[%s] auto-picked %d initial panels for downstream (outfits=%s)",
                        template_id, len(picked), [e["outfit_index"] for e in picked],
                    )
            elif initial_remix_ids and lookbooks:
                # 断点续跑：从 lookbooks 里反查这些 remix_id 对应的 panel，重建 outfit_shots
                picked_urls: list[dict] = []
                for rid in initial_remix_ids:
                    for lb in lookbooks:
                        match = next((p for p in lb["panels"] if p.get("used_in_remix_id") == rid), None)
                        if match:
                            picked_urls.append({
                                "image_url": match["image_url"],
                                "frame_index": None,
                                "group_frame_indices": [],
                            })
                            break
                if picked_urls:
                    outfit_shots = picked_urls
                    state["outfit_shots"] = picked_urls
                    logger.info("[%s] resumed: %d panels restored for downstream", template_id, len(picked_urls))

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

            # 阶段 2.5 auto-initial remix_history 行翻 status=success
            await _finalize_initial_remixes(template_id, success=True)

            # 最终持久化
            await _persist_states([template_id])

            # 如果是"一键重新分析"触发的，同步 shots 到关联 video_tasks。
            # 先看内存，再回退 DB tpl.extra["sync_shots_to_tasks"]，
            # 确保重启后续跑的模板也能命中。
            should_sync_shots = template_id in _sync_shots_on_success
            _sync_shots_on_success.discard(template_id)
            if not should_sync_shots:
                async with SessionLocal() as session:
                    tpl = await session.get(VideoAITemplate, uuid_val)
                    if tpl and isinstance(tpl.extra, dict) and tpl.extra.get("sync_shots_to_tasks"):
                        should_sync_shots = True
            if should_sync_shots:
                _final_outfits = state.get("final_outfits") or []
                await _sync_task_shots(
                    template_id,
                    uuid_val,
                    _final_outfits,
                    state.get("prompt_description") or "",
                )
            # 模板成功跑完 → 取消"失败时废弃关联视频任务"的标记 + 清 DB 登记
            _abandon_task_ids_on_fail.pop(template_id, None)
            try:
                async with SessionLocal() as session:
                    tpl = await session.get(VideoAITemplate, uuid_val)
                    if tpl and isinstance(tpl.extra, dict) and (
                        "abandon_task_ids_on_fail" in tpl.extra
                        or "sync_shots_to_tasks" in tpl.extra
                    ):
                        cleaned = dict(tpl.extra)
                        cleaned.pop("abandon_task_ids_on_fail", None)
                        cleaned.pop("sync_shots_to_tasks", None)
                        tpl.extra = cleaned
                        await session.commit()
            except Exception as exc:
                logger.warning("[%s] failed to clear backfill flags on success: %s", template_id, exc)

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
            # 阶段 2.5 auto-initial remix_history 行翻 status=failed
            try:
                await _finalize_initial_remixes(template_id, success=False, error_message=str(exc))
            except Exception:
                logger.exception("[%s] _finalize_initial_remixes failed", template_id)
            await _persist_states([template_id])
            await _abandon_linked_tasks_if_marked(template_id)
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


async def enqueue_template(
    template_id: str,
    *,
    clear_stages: bool = False,
    cta: bool | None = None,
) -> None:
    """
    将模板加入队列并标记为等待中。

    Args:
        template_id: 模板 ID
        clear_stages: 为 True 时清空 completed_stages，从头重跑；默认 False（断点续跑）
        cta: True=走「有CTA」一套提示词，False=「无CTA」。
             None=保留 state 中已存的值（断点续跑场景必须如此，否则会被默认值覆盖）；
             首次入队 + state 中没有 cta 时按 False 处理。
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
                    logger.info("[%s] restored state from DB: completed_stages=%s cta=%s",
                                template_id, saved.get("completed_stages", []), saved.get("cta"))
        except Exception as exc:
            logger.warning("[%s] failed to restore state from DB: %s", template_id, exc)

    # 保留已有 state（保留 completed_stages 和已产出数据）
    state = video_ai_states.setdefault(template_id, _new_state(template_id, VideoAIProcessStatus.pending))

    # cta 注入策略：
    #   - clear_stages=True（restart_template / 一键重试）→ 始终用传入值（None 视作 False）
    #   - clear_stages=False（resume / recover_stuck）→ None 表示保留已有值；显式 True/False 才覆盖
    if clear_stages or cta is not None:
        state["cta"] = bool(cta)
    elif "cta" not in state:
        state["cta"] = False
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


async def restart_template(template_id: str, *, cta: bool = False) -> None:
    """
    从头重跑：清空已完成阶段，重新执行所有步骤。
    cta：True=走「有CTA」一套提示词。
    """
    await enqueue_template(template_id, clear_stages=True, cta=cta)


async def restart_from_stage2(template_id: str, *, cta: bool = False) -> None:
    """
    重新生图：清除全部已完成阶段与中间产物，从头开始整条流水线。

    新管道下视频理解依赖 outfit_detailing 输出，无法再独立保留，因此与
    `restart_template` 行为一致——保留入口名以兼容现有调用方/前端按钮。
    """
    await enqueue_template(template_id, clear_stages=True, cta=cta)
    logger.info("[%s] restart_from_stage2 (full reset) enqueued cta=%s", template_id, cta)


async def batch_restart_templates(
    owner_id: str | None = None,
    template_ids: list[str] | None = None,
    abandon_task_ids_on_fail: dict[str, list[str]] | None = None,
    cta_map: dict[str, bool] | None = None,
) -> dict:
    """
    批量全流程重跑：入队 → 等待每个 pipeline 完成 → 同步 shots 到关联 video_tasks。
    传入 template_ids 则只处理这些模板；否则处理该 owner 所有模板。
    abandon_task_ids_on_fail：{template_id: [video_task_id, ...]}，仅 daily-tasks
    "一键重试" 使用——通过 _abandon_task_ids_on_fail 标记集传给
    `_sync_task_shots` 在管道结束时统一处理（成功不影响、失败则 abandoned）。
    cta_map：{template_id: cta_bool}，daily-tasks 一键重试时按 video_task.cta
    决定该模板这次走哪一套提示词；为空 / 找不到 → 默认 False（无CTA）。
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

    if abandon_task_ids_on_fail:
        for _tid in tids:
            mapped = abandon_task_ids_on_fail.get(_tid)
            if mapped:
                _abandon_task_ids_on_fail[_tid] = list(mapped)

    # 同步把「成功后同步 shots」+「失败时废弃 task_ids」持久化到 DB tpl.extra，
    # 后端重启后这些状态不会丢；管道在终态再清掉。
    try:
        async with SessionLocal() as session:
            tpl_rows = (await session.execute(
                sa_select(VideoAITemplate).where(
                    VideoAITemplate.id.in_([UUID(tid) for tid in tids])
                )
            )).scalars().all()
            tpl_map = {str(t.id): t for t in tpl_rows}
            for _tid in tids:
                tpl = tpl_map.get(_tid)
                if tpl is None:
                    continue
                extra = dict(tpl.extra or {})
                extra["sync_shots_to_tasks"] = True
                mapped = (abandon_task_ids_on_fail or {}).get(_tid)
                if mapped:
                    extra["abandon_task_ids_on_fail"] = list(mapped)
                else:
                    extra.pop("abandon_task_ids_on_fail", None)
                tpl.extra = extra
            await session.commit()
    except Exception as exc:
        logger.warning("batch_restart: failed to persist sync flags to DB: %s", exc)

    logger.info("batch_restart started: %d templates", len(tids))
    success_count = 0
    fail_count = 0
    cta_map = cta_map or {}
    for tid in tids:
        try:
            _sync_shots_on_success.add(tid)
            await restart_template(tid, cta=bool(cta_map.get(tid, False)))
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
        VideoAIProcessStatus.lookbook_gen,   # 阶段 2.5
        VideoAIProcessStatus.remixing,        # 阶段 2.5 后的下游
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
