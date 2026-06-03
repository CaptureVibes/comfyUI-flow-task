"""persona_tagging_queue_service.py

视频/博主人设打标队列处理器。
从 video_tagging_results / blogger_tagging_results 表中拉取 pending 任务并执行。
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.models.persona_tagging import BloggerTaggingResult, VideoTaggingResult
from app.models.tiktok_blogger import TiktokBlogger
from app.models.video_source import VideoSource
from app.services.persona_tagging_service import (
    aggregate_classifications,
    aggregate_style_results,
    analyze_blogger_account,
    analyze_video_classification,
    analyze_video_description_unit,
    analyze_video_style_signature,
    analyze_video_style_vector,
    get_blogger_videos,
    merge_blogger_personal_tags,
)

logger = logging.getLogger("app.persona_tagging_queue")

_TASK_LOCK_SECONDS = 3600
_POLL_INTERVAL = 5

_video_processor_task: asyncio.Task | None = None
_blogger_processor_task: asyncio.Task | None = None
_shutting_down = False


# ── 任务领取（SELECT ... FOR UPDATE SKIP LOCKED）──────────────────────────────

async def _claim_next_video_task(db: AsyncSession, worker_id: str) -> VideoTaggingResult | None:
    now = datetime.now(timezone.utc)
    lock_until = now + timedelta(seconds=_TASK_LOCK_SECONDS)

    result = await db.execute(
        select(VideoTaggingResult)
        .where(
            or_(
                VideoTaggingResult.status == "pending",
                and_(
                    VideoTaggingResult.status == "running",
                    or_(
                        VideoTaggingResult.lock_until.is_(None),
                        VideoTaggingResult.lock_until < now,
                    ),
                ),
            ),
            or_(
                VideoTaggingResult.next_retry_at.is_(None),
                VideoTaggingResult.next_retry_at <= now,
            ),
        )
        .order_by(VideoTaggingResult.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    task = result.scalar_one_or_none()
    if task is None:
        return None

    task.status = "running"
    task.result_message = "running"
    task.worker_id = worker_id
    task.lock_until = lock_until
    task.attempts = (task.attempts or 0) + 1
    if task.started_at is None:
        task.started_at = now
    task.updated_at = now
    await db.commit()
    await db.refresh(task)
    return task


async def _claim_next_blogger_task(db: AsyncSession, worker_id: str) -> BloggerTaggingResult | None:
    now = datetime.now(timezone.utc)
    lock_until = now + timedelta(seconds=_TASK_LOCK_SECONDS)

    result = await db.execute(
        select(BloggerTaggingResult)
        .where(
            or_(
                BloggerTaggingResult.status == "pending",
                and_(
                    BloggerTaggingResult.status == "waiting_videos",
                    or_(
                        BloggerTaggingResult.next_retry_at.is_(None),
                        BloggerTaggingResult.next_retry_at <= now,
                    ),
                ),
                and_(
                    BloggerTaggingResult.status.in_(["checking_videos", "aggregating"]),
                    or_(
                        BloggerTaggingResult.lock_until.is_(None),
                        BloggerTaggingResult.lock_until < now,
                    ),
                ),
            )
        )
        .order_by(BloggerTaggingResult.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    task = result.scalar_one_or_none()
    if task is None:
        return None

    task.status = "checking_videos"
    task.result_message = "checking videos"
    task.worker_id = worker_id
    task.lock_until = lock_until
    task.attempts = (task.attempts or 0) + 1
    if task.started_at is None:
        task.started_at = now
    task.updated_at = now
    await db.commit()
    await db.refresh(task)
    return task


# ── 单视频打标任务执行 ─────────────────────────────────────────────────────────

async def _run_video_task(task_id: uuid.UUID) -> None:
    raw_outputs: dict = {}
    async with SessionLocal() as db:
        result = await db.execute(select(VideoTaggingResult).where(VideoTaggingResult.id == task_id))
        task = result.scalar_one_or_none()
        if task is None:
            return

        try:
            video_url = task.gcs_url
            caption = task.description
            hashtag = ""

            # 阶段1：生成描述单元（需要视频内容）
            unit_result = await analyze_video_description_unit(
                video_url=video_url,
                gcs_url=task.gcs_url,
                caption=caption,
                hashtag=hashtag,
                video_index=1,
            )
            raw_outputs["video_description_unit"] = unit_result
            if unit_result.get("error"):
                raise RuntimeError(f"video_description_unit: {unit_result['error']}")
            unit = unit_result.get("parsed") or {}

            # 阶段3：10 属性分类（纯文本，用描述单元）
            classification_result = await analyze_video_classification(
                video_url=video_url,
                caption=caption,
                hashtag=hashtag,
                unit=unit,
            )
            raw_outputs["personal_tags"] = classification_result
            if classification_result.get("error"):
                raise RuntimeError(f"personal_tags: {classification_result['error']}")
            personal_tags = classification_result.get("parsed") or {}

            # 阶段4：32 维风格向量
            style_vector_result = await analyze_video_style_vector(
                video_url=video_url,
                caption=caption,
                hashtag=hashtag,
                unit=unit,
            )
            raw_outputs["style_vector"] = style_vector_result
            if style_vector_result.get("error"):
                raise RuntimeError(f"style_vector: {style_vector_result['error']}")
            style_vector = style_vector_result.get("parsed") or {}

            # 阶段5：风格签名
            style_signature_result = await analyze_video_style_signature(
                video_url=video_url,
                caption=caption,
                hashtag=hashtag,
                unit=unit,
                style_vector=style_vector,
            )
            raw_outputs["style_signature"] = style_signature_result
            if style_signature_result.get("error"):
                raise RuntimeError(f"style_signature: {style_signature_result['error']}")
            style_signature = style_signature_result.get("parsed") or {}

            now = datetime.now(timezone.utc)
            task.status = "success"
            task.result_code = 0
            task.result_message = "video tagging completed"
            task.error_code = None
            task.error_message = None
            task.video_description_unit = unit
            task.personal_tags = personal_tags
            task.style_vector = style_vector
            task.style_signature = style_signature
            task.raw_outputs = raw_outputs
            task.worker_id = None
            task.lock_until = None
            task.finished_at = now
            task.updated_at = now

            # 写回 video_sources 表
            vs_result = await db.execute(
                select(VideoSource).where(VideoSource.id == task.video_id)
            )
            vs = vs_result.scalar_one_or_none()
            if vs is not None:
                vs.personal_tags = personal_tags
                vs.style_vector = style_vector
                vs.tagging_status = "success"
                vs.updated_at = now

            logger.info("Video tagging success: task_id=%s video_id=%s", task_id, task.video_id)

        except Exception as exc:
            logger.exception("Video tagging failed: task_id=%s err=%s", task_id, exc)
            now = datetime.now(timezone.utc)
            task.status = "failed"
            task.result_code = 5000
            task.result_message = str(exc)
            task.error_code = "5000"
            task.error_message = str(exc)
            task.raw_outputs = raw_outputs
            task.worker_id = None
            task.lock_until = None
            task.finished_at = now
            task.updated_at = now

            # 写回失败状态
            try:
                vs_result = await db.execute(
                    select(VideoSource).where(VideoSource.id == task.video_id)
                )
                vs = vs_result.scalar_one_or_none()
                if vs is not None:
                    vs.tagging_status = "failed"
                    vs.updated_at = now
            except Exception:
                pass

        await db.commit()


# ── 博主打标任务执行 ───────────────────────────────────────────────────────────

async def _get_or_create_video_task(
    db: AsyncSession,
    video_id: str,
    gcs_url: str,
    description: str,
    blogger_task_id: uuid.UUID,
    tiktok_blogger_id: uuid.UUID,
) -> VideoTaggingResult:
    """确保视频打标任务存在；若已存在则复用。"""
    vid_uuid = uuid.UUID(video_id)
    result = await db.execute(
        select(VideoTaggingResult).where(VideoTaggingResult.video_id == vid_uuid)
    )
    existing = result.scalar_one_or_none()

    if existing and existing.status == "success":
        return existing
    if existing and existing.status in ("pending", "running"):
        return existing

    now = datetime.now(timezone.utc)
    if existing:
        existing.gcs_url = gcs_url
        existing.description = description
        existing.status = "pending"
        existing.result_code = 0
        existing.result_message = "received"
        existing.error_code = None
        existing.error_message = None
        existing.source_type = "blogger"
        existing.source_blogger_task_id = blogger_task_id
        existing.source_tiktok_blogger_id = tiktok_blogger_id
        existing.worker_id = None
        existing.lock_until = None
        existing.started_at = None
        existing.finished_at = None
        existing.updated_at = now
        return existing

    new_task = VideoTaggingResult(
        id=uuid.uuid4(),
        video_id=vid_uuid,
        gcs_url=gcs_url,
        description=description,
        status="pending",
        result_code=0,
        result_message="received",
        source_type="blogger",
        source_blogger_task_id=blogger_task_id,
        source_tiktok_blogger_id=tiktok_blogger_id,
        created_at=now,
        updated_at=now,
    )
    db.add(new_task)
    return new_task


async def _wait_for_video_tasks(
    blogger_task_id: uuid.UUID,
    video_task_ids: list[uuid.UUID],
    min_success: int,
    max_wait_seconds: int = 3600,
) -> list[VideoTaggingResult]:
    """轮询等待视频打标完成，直到成功数量满足要求或超时。"""
    deadline = datetime.now(timezone.utc) + timedelta(seconds=max_wait_seconds)
    while datetime.now(timezone.utc) < deadline:
        async with SessionLocal() as db:
            result = await db.execute(
                select(VideoTaggingResult).where(
                    VideoTaggingResult.id.in_(video_task_ids)
                )
            )
            tasks = result.scalars().all()
            success = [t for t in tasks if t.status == "success"]
            if len(success) >= min_success:
                return list(success)
            all_done = all(t.status in ("success", "failed") for t in tasks)
            if all_done:
                return list(success)
        await asyncio.sleep(10)
    return []


async def _run_blogger_task(task_id: uuid.UUID) -> None:
    async with SessionLocal() as db:
        result = await db.execute(select(BloggerTaggingResult).where(BloggerTaggingResult.id == task_id))
        task = result.scalar_one_or_none()
        if task is None:
            return

        try:
            tiktok_blogger_id = task.tiktok_blogger_id
            min_count = task.min_video_count or 15

            # 检查博主是否存在
            blogger_result = await db.execute(
                select(TiktokBlogger).where(TiktokBlogger.id == tiktok_blogger_id)
            )
            blogger = blogger_result.scalar_one_or_none()
            if blogger is None:
                raise RuntimeError(f"blogger not found: {tiktok_blogger_id}")

            # 获取博主视频列表
            videos = await get_blogger_videos(db, tiktok_blogger_id)
            available = len(videos)
            now = datetime.now(timezone.utc)

            task.available_video_count = available
            task.usable_video_count = available
            task.updated_at = now

            if available < min_count:
                task.status = "failed"
                task.result_code = 4202
                task.result_message = "insufficient videos"
                task.error_code = "4202"
                task.error_message = f"available={available} < required={min_count}"
                task.worker_id = None
                task.lock_until = None
                task.finished_at = now
                await db.commit()
                return

            # 查已有打标结果
            video_ids = [uuid.UUID(v["video_id"]) for v in videos]
            existing_result = await db.execute(
                select(VideoTaggingResult).where(VideoTaggingResult.video_id.in_(video_ids))
            )
            existing_by_video = {str(t.video_id): t for t in existing_result.scalars().all()}

            success_tasks = [t for t in existing_by_video.values() if t.status == "success"]

            if len(success_tasks) < min_count:
                # 提交缺少的视频打标任务
                needed = min_count - len(success_tasks)
                missing_videos = [
                    v for v in videos
                    if existing_by_video.get(v["video_id"]) is None
                    or existing_by_video[v["video_id"]].status not in ("success", "pending", "running")
                ][:needed]

                video_task_ids: list[uuid.UUID] = []
                for video in missing_videos:
                    vt = await _get_or_create_video_task(
                        db,
                        video_id=video["video_id"],
                        gcs_url=video["gcs_url"],
                        description=video["description"],
                        blogger_task_id=task_id,
                        tiktok_blogger_id=tiktok_blogger_id,
                    )
                    video_task_ids.append(vt.id)

                await db.commit()

                task.status = "waiting_videos"
                task.result_code = 0
                task.result_message = "waiting for video tagging"
                task.successful_video_count = len(success_tasks)
                task.submitted_video_count = len(video_task_ids)
                task.video_task_ids = [str(tid) for tid in video_task_ids]
                task.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=30)
                task.worker_id = None
                task.lock_until = None
                task.updated_at = datetime.now(timezone.utc)
                await db.commit()
                return

            # 已有足够成功视频，开始聚合
            task.status = "aggregating"
            task.result_message = "aggregating blogger result"
            task.successful_video_count = len(success_tasks)
            task.selected_video_ids = [str(t.video_id) for t in success_tasks[:min_count]]
            task.updated_at = datetime.now(timezone.utc)
            await db.commit()

            selected = success_tasks[:min_count]

            units = [t.video_description_unit for t in selected if t.video_description_unit]
            account_result = await analyze_blogger_account(units)
            if account_result.get("error"):
                raise RuntimeError(f"blogger_account: {account_result['error']}")
            account_parsed = account_result.get("parsed") or {}

            classification_inputs = [
                {"parsed": t.personal_tags, "error": ""} for t in selected
            ]
            classification_summary = aggregate_classifications(classification_inputs)

            style_vector_inputs = [
                {"parsed": t.style_vector, "error": ""} for t in selected
            ]
            style_signature_inputs = [
                {"parsed": t.style_signature, "error": ""} for t in selected
            ]
            style_summary = aggregate_style_results(style_vector_inputs, style_signature_inputs)

            account_personal_tags = merge_blogger_personal_tags(account_parsed, classification_summary)

            now = datetime.now(timezone.utc)
            task.status = "success"
            task.result_code = 0
            task.result_message = "blogger tagging completed"
            task.error_code = None
            task.error_message = None
            task.account_personal_tags = account_personal_tags
            task.account_style_vector = style_summary.get("average_style_vector") or {}
            task.account_style_signature = style_summary.get("account_style_signature") or {}
            task.aggregated_social_identity = classification_summary.get("social_identity") or {}
            task.aggregated_occasion = classification_summary.get("occasion") or {}
            task.raw_outputs = {
                "account_result": account_result,
                "style_summary": style_summary,
            }
            task.worker_id = None
            task.lock_until = None
            task.finished_at = now
            task.updated_at = now

            # 写回 tiktok_bloggers 表
            blogger_row = await db.execute(
                select(TiktokBlogger).where(TiktokBlogger.id == tiktok_blogger_id)
            )
            blogger_obj = blogger_row.scalar_one_or_none()
            if blogger_obj is not None:
                blogger_obj.persona_tags = account_personal_tags
                blogger_obj.style_vector = style_summary.get("average_style_vector") or {}
                blogger_obj.style_signature = style_summary.get("account_style_signature") or {}
                blogger_obj.tagging_status = "success"
                blogger_obj.updated_at = now

            logger.info("Blogger tagging success: task_id=%s blogger_id=%s", task_id, tiktok_blogger_id)

        except Exception as exc:
            logger.exception("Blogger tagging failed: task_id=%s err=%s", task_id, exc)
            now = datetime.now(timezone.utc)
            task.status = "failed"
            task.result_code = 5000
            task.result_message = str(exc)
            task.error_code = "5000"
            task.error_message = str(exc)
            task.worker_id = None
            task.lock_until = None
            task.finished_at = now
            task.updated_at = now

            # 写回失败状态
            try:
                blogger_row = await db.execute(
                    select(TiktokBlogger).where(TiktokBlogger.id == task.tiktok_blogger_id)
                )
                blogger_obj = blogger_row.scalar_one_or_none()
                if blogger_obj is not None:
                    blogger_obj.tagging_status = "failed"
                    blogger_obj.updated_at = now
            except Exception:
                pass

        await db.commit()


# ── Worker 循环 ────────────────────────────────────────────────────────────────

async def _video_worker_loop() -> None:
    worker_id = f"video-persona-{id(asyncio.current_task())}"
    logger.info("Video persona tagging worker started: %s", worker_id)
    while not _shutting_down:
        try:
            async with SessionLocal() as db:
                task = await _claim_next_video_task(db, worker_id)
            if task is None:
                await asyncio.sleep(_POLL_INTERVAL)
                continue
            await _run_video_task(task.id)
        except Exception as exc:
            logger.exception("Video worker error: %s", exc)
            await asyncio.sleep(_POLL_INTERVAL)


async def _blogger_worker_loop() -> None:
    worker_id = f"blogger-persona-{id(asyncio.current_task())}"
    logger.info("Blogger persona tagging worker started: %s", worker_id)
    while not _shutting_down:
        try:
            async with SessionLocal() as db:
                task = await _claim_next_blogger_task(db, worker_id)
            if task is None:
                await asyncio.sleep(_POLL_INTERVAL)
                continue
            await _run_blogger_task(task.id)
        except Exception as exc:
            logger.exception("Blogger worker error: %s", exc)
            await asyncio.sleep(_POLL_INTERVAL)


# ── 启动 / 停止 ────────────────────────────────────────────────────────────────

def start_persona_tagging_workers() -> None:
    global _video_processor_task, _blogger_processor_task, _shutting_down
    _shutting_down = False
    if _video_processor_task is None or _video_processor_task.done():
        _video_processor_task = asyncio.create_task(_video_worker_loop())
    if _blogger_processor_task is None or _blogger_processor_task.done():
        _blogger_processor_task = asyncio.create_task(_blogger_worker_loop())
    logger.info("Persona tagging workers started")


async def stop_persona_tagging_workers() -> None:
    global _shutting_down
    _shutting_down = True
    for t in (_video_processor_task, _blogger_processor_task):
        if t and not t.done():
            t.cancel()
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
    logger.info("Persona tagging workers stopped")


async def recover_stuck_tagging_on_startup() -> None:
    """启动时将残留 running 状态的任务重置为 pending。"""
    async with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        await db.execute(
            update(VideoTaggingResult)
            .where(VideoTaggingResult.status == "running")
            .values(
                status="pending",
                result_message="recovered after restart",
                worker_id=None,
                lock_until=None,
                updated_at=now,
            )
        )
        await db.execute(
            update(BloggerTaggingResult)
            .where(BloggerTaggingResult.status.in_(["running", "checking_videos", "aggregating"]))
            .values(
                status="pending",
                result_message="recovered after restart",
                worker_id=None,
                lock_until=None,
                updated_at=now,
            )
        )
        await db.commit()
    logger.info("Recovered stuck persona tagging tasks on startup")
