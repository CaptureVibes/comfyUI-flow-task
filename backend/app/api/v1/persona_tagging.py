"""persona_tagging.py

人设打标 API 路由。
- POST /persona-tagging/videos/{video_id}/tag     — 提交单视频打标任务
- GET  /persona-tagging/videos/{video_id}         — 查询单视频打标结果
- POST /persona-tagging/bloggers/{blogger_id}/tag — 提交博主打标任务
- GET  /persona-tagging/bloggers/{blogger_id}     — 查询博主打标结果
- GET  /persona-tagging/videos                    — 列出视频打标任务（管理）
- GET  /persona-tagging/bloggers                  — 列出博主打标任务（管理）
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenData, get_current_user
from app.db.session import get_db
from app.models.persona_tagging import BloggerTaggingResult, VideoTaggingResult
from app.models.tiktok_blogger import TiktokBlogger
from app.models.video_source import VideoSource
from app.services.persona_tagging_service import get_blogger_videos

router = APIRouter(prefix="/persona-tagging", tags=["persona-tagging"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── 视频打标 ───────────────────────────────────────────────────────────────────

@router.post("/videos/{video_id}/tag", status_code=201)
async def submit_video_tagging(
    video_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> dict[str, Any]:
    """提交单视频人设打标任务。如果已有成功结果则直接返回。"""
    # 查找视频源
    result = await db.execute(select(VideoSource).where(VideoSource.id == video_id))
    video = result.scalar_one_or_none()
    if video is None:
        raise HTTPException(status_code=404, detail="video not found")

    if not video.local_gcs_video_url:
        raise HTTPException(status_code=422, detail="video has no GCS URL (not uploaded yet)")

    description = video.video_desc or video.video_title or ""
    if not description:
        raise HTTPException(status_code=422, detail="video has no description or title")

    # 查已有任务
    existing_result = await db.execute(
        select(VideoTaggingResult).where(VideoTaggingResult.video_id == video_id)
    )
    existing = existing_result.scalar_one_or_none()

    if existing and existing.status == "success":
        return {"code": 0, "message": "already_processed", "task": _video_task_dict(existing)}
    if existing and existing.status in ("pending", "running"):
        return {"code": 0, "message": "already_running", "task": _video_task_dict(existing)}

    now = _utcnow()

    # 更新视频的打标状态为 pending
    video.tagging_status = "pending"
    video.updated_at = now

    if existing:
        existing.gcs_url = video.local_gcs_video_url
        existing.description = description
        existing.status = "pending"
        existing.result_code = 0
        existing.result_message = "received"
        existing.error_code = None
        existing.error_message = None
        existing.source_type = "direct"
        existing.worker_id = None
        existing.lock_until = None
        existing.started_at = None
        existing.finished_at = None
        existing.updated_at = now
        task = existing
    else:
        task = VideoTaggingResult(
            id=uuid.uuid4(),
            video_id=video_id,
            gcs_url=video.local_gcs_video_url,
            description=description,
            status="pending",
            result_code=0,
            result_message="received",
            source_type="direct",
            created_at=now,
            updated_at=now,
        )
        db.add(task)

    await db.commit()
    await db.refresh(task)
    return {"code": 0, "message": "received", "task": _video_task_dict(task)}


@router.get("/videos/{video_id}")
async def get_video_tagging(
    video_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> dict[str, Any]:
    """查询视频打标结果（以 video_source.id 为 key）。"""
    result = await db.execute(
        select(VideoTaggingResult).where(VideoTaggingResult.video_id == video_id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="tagging task not found")
    return {"code": 0, "data": _video_task_dict(task)}


@router.get("/videos")
async def list_video_taggings(
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> dict[str, Any]:
    """列出视频打标任务（管理用）。"""
    stmt = select(VideoTaggingResult)
    if status:
        stmt = stmt.where(VideoTaggingResult.status == status)
    stmt = stmt.order_by(VideoTaggingResult.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    return {"code": 0, "data": [_video_task_dict(t) for t in tasks], "total": len(tasks)}


# ── 博主打标 ───────────────────────────────────────────────────────────────────

@router.post("/bloggers/{blogger_id}/tag", status_code=201)
async def submit_blogger_tagging(
    blogger_id: uuid.UUID,
    min_video_count: int = Query(15, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> dict[str, Any]:
    """提交博主账号级人设打标任务。"""
    # 校验博主存在
    blogger_result = await db.execute(select(TiktokBlogger).where(TiktokBlogger.id == blogger_id))
    blogger = blogger_result.scalar_one_or_none()
    if blogger is None:
        raise HTTPException(status_code=404, detail="blogger not found")

    # 检查可用视频数量
    videos = await get_blogger_videos(db, blogger_id)
    available = len(videos)
    if available < min_video_count:
        raise HTTPException(
            status_code=422,
            detail=f"insufficient videos: available={available}, required={min_video_count}",
        )

    # 查已有任务
    existing_result = await db.execute(
        select(BloggerTaggingResult).where(BloggerTaggingResult.tiktok_blogger_id == blogger_id)
    )
    existing = existing_result.scalar_one_or_none()

    if existing and existing.status == "success":
        return {"code": 0, "message": "already_processed", "task": _blogger_task_dict(existing)}
    if existing and existing.status in ("pending", "checking_videos", "waiting_videos", "aggregating"):
        return {"code": 0, "message": "already_running", "task": _blogger_task_dict(existing)}

    now = _utcnow()

    # 更新博主的打标状态为 pending
    blogger.tagging_status = "pending"
    blogger.updated_at = now

    if existing:
        existing.min_video_count = min_video_count
        existing.available_video_count = available
        existing.usable_video_count = available
        existing.status = "pending"
        existing.result_code = 0
        existing.result_message = "received"
        existing.error_code = None
        existing.error_message = None
        existing.worker_id = None
        existing.lock_until = None
        existing.next_retry_at = None
        existing.started_at = None
        existing.finished_at = None
        existing.updated_at = now
        task = existing
    else:
        task = BloggerTaggingResult(
            id=uuid.uuid4(),
            tiktok_blogger_id=blogger_id,
            min_video_count=min_video_count,
            available_video_count=available,
            usable_video_count=available,
            status="pending",
            result_code=0,
            result_message="received",
            created_at=now,
            updated_at=now,
        )
        db.add(task)

    await db.commit()
    await db.refresh(task)
    return {"code": 0, "message": "received", "task": _blogger_task_dict(task)}


@router.get("/bloggers/{blogger_id}")
async def get_blogger_tagging(
    blogger_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> dict[str, Any]:
    """查询博主打标结果。"""
    result = await db.execute(
        select(BloggerTaggingResult).where(BloggerTaggingResult.tiktok_blogger_id == blogger_id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="tagging task not found")
    return {"code": 0, "data": _blogger_task_dict(task)}


@router.get("/bloggers/{blogger_id}/progress")
async def get_blogger_tagging_progress(
    blogger_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> dict[str, Any]:
    """
    查询博主打标进度：任务整体状态 + 每条视频的打标状态。
    用于前端进度弹窗轮询。
    """
    # 博主任务
    task_result = await db.execute(
        select(BloggerTaggingResult).where(BloggerTaggingResult.tiktok_blogger_id == blogger_id)
    )
    task = task_result.scalar_one_or_none()

    # 博主旗下所有视频（有 URL + 描述的）
    videos = await get_blogger_videos(db, blogger_id)
    video_ids = [uuid.UUID(v["video_id"]) for v in videos]

    # 批量查视频打标任务
    video_tasks_result = await db.execute(
        select(VideoTaggingResult).where(VideoTaggingResult.video_id.in_(video_ids))
    )
    video_tasks_by_id = {str(t.video_id): t for t in video_tasks_result.scalars().all()}

    # 构建每个视频的进度条目
    video_items = []
    for v in videos:
        vt = video_tasks_by_id.get(v["video_id"])
        video_items.append({
            "video_id": v["video_id"],
            "description": v["description"][:60] + ("…" if len(v["description"]) > 60 else ""),
            "status": vt.status if vt else "not_started",
            "error_message": vt.error_message if vt else None,
            "updated_at": vt.updated_at.isoformat() if vt and vt.updated_at else None,
        })

    # 统计各状态数量
    status_counts: dict[str, int] = {}
    for item in video_items:
        s = item["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    total = len(video_items)
    summary = {
        "total": total,
        "success": status_counts.get("success", 0),
        "failed": status_counts.get("failed", 0),
        "running": status_counts.get("running", 0),
        "pending": status_counts.get("pending", 0),
        "not_started": status_counts.get("not_started", 0),
    }

    # 整体打标状态
    blogger_status = task.status if task else "not_started"
    is_active = blogger_status in ("pending", "checking_videos", "waiting_videos", "aggregating", "running")

    return {
        "code": 0,
        "data": {
            "blogger_id": str(blogger_id),
            "blogger_status": blogger_status,
            "is_active": is_active,
            "summary": summary,
            "videos": video_items,
            "min_video_count": task.min_video_count if task else 15,
            "started_at": task.started_at.isoformat() if task and task.started_at else None,
            "finished_at": task.finished_at.isoformat() if task and task.finished_at else None,
        },
    }


@router.get("/bloggers")
async def list_blogger_taggings(
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> dict[str, Any]:
    """列出博主打标任务（管理用）。"""
    stmt = select(BloggerTaggingResult)
    if status:
        stmt = stmt.where(BloggerTaggingResult.status == status)
    stmt = stmt.order_by(BloggerTaggingResult.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    return {"code": 0, "data": [_blogger_task_dict(t) for t in tasks], "total": len(tasks)}


# ── 序列化工具 ─────────────────────────────────────────────────────────────────

def _video_task_dict(task: VideoTaggingResult) -> dict[str, Any]:
    return {
        "id": str(task.id),
        "video_id": str(task.video_id),
        "gcs_url": task.gcs_url,
        "status": task.status,
        "result_code": task.result_code,
        "result_message": task.result_message,
        "error_code": task.error_code,
        "error_message": task.error_message,
        "video_description_unit": task.video_description_unit,
        "personal_tags": task.personal_tags,
        "style_vector": task.style_vector,
        "style_signature": task.style_signature,
        "source_type": task.source_type,
        "attempts": task.attempts,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
    }


def _blogger_task_dict(task: BloggerTaggingResult) -> dict[str, Any]:
    return {
        "id": str(task.id),
        "tiktok_blogger_id": str(task.tiktok_blogger_id),
        "status": task.status,
        "result_code": task.result_code,
        "result_message": task.result_message,
        "error_code": task.error_code,
        "error_message": task.error_message,
        "min_video_count": task.min_video_count,
        "available_video_count": task.available_video_count,
        "successful_video_count": task.successful_video_count,
        "failed_video_count": task.failed_video_count,
        "submitted_video_count": task.submitted_video_count,
        "selected_video_ids": [str(v) for v in (task.selected_video_ids or [])],
        "account_personal_tags": task.account_personal_tags,
        "account_style_vector": task.account_style_vector,
        "account_style_signature": task.account_style_signature,
        "aggregated_social_identity": task.aggregated_social_identity,
        "aggregated_occasion": task.aggregated_occasion,
        "attempts": task.attempts,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
    }
