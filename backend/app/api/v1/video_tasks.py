from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenData, get_current_user
from app.db.session import get_db
from app.schemas.video_task import (
    VideoSubTaskRead,
    VideoSubTaskStatusUpdate,
    VideoTaskCreate,
    VideoTaskDetailRead,
    VideoTaskListItem,
    VideoTaskRead,
    VideoTaskStateRead,
)
from app.services.video_task_service import VideoTaskService

router = APIRouter(prefix="/video-tasks", tags=["video-tasks"])


def _get_creator_id(current_user: TokenData = Depends(get_current_user)) -> uuid.UUID:
    return current_user.user_id


def _get_query_owner_id(current_user: TokenData = Depends(get_current_user)) -> uuid.UUID | None:
    return None if current_user.is_admin else current_user.user_id


# ── Parent task endpoints ──────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED, response_model=VideoTaskDetailRead)
async def create_video_task(
    payload: VideoTaskCreate,
    creator_id: uuid.UUID = Depends(_get_creator_id),
    session: AsyncSession = Depends(get_db),
) -> Any:
    svc = VideoTaskService(db=session)
    task = await svc.create_task(
        account_id=payload.account_id,
        template_id=payload.template_id,
        final_prompt=payload.final_prompt,
        duration=payload.duration,
        shots=payload.shots,
        user_id=creator_id,
    )
    return task


@router.get("", response_model=list[VideoTaskListItem])
async def list_video_tasks(
    target_date: date | None = Query(default=None),
    account_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    tiktok_blogger_id: uuid.UUID | None = Query(default=None),
    owner_id: uuid.UUID | None = Depends(_get_query_owner_id),
    session: AsyncSession = Depends(get_db),
) -> Any:
    svc = VideoTaskService(db=session)
    enriched = await svc.get_tasks_with_names(target_date, owner_id, account_id, status, tiktok_blogger_id)
    result = []
    for item in enriched:
        task = item["task"]
        data = VideoTaskListItem.model_validate(task)
        data.account_name = item["account_name"]
        data.template_title = item["template_title"]
        data.sub_tasks_done = item["sub_tasks_done"]
        result.append(data)
    return result


@router.get("/stats", response_model=dict[str, int])
async def get_video_task_stats(
    target_date: date | None = Query(default=None),
    tiktok_blogger_id: uuid.UUID | None = Query(default=None),
    owner_id: uuid.UUID | None = Depends(_get_query_owner_id),
    session: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Return count per status, optionally filtered by target_date and tiktok_blogger_id."""
    from sqlalchemy import func, select
    from app.models.video_task import VideoTask
    from app.models.video_ai_template import VideoAITemplate

    stmt = select(
        VideoTask.status,
        func.count(VideoTask.id).label("cnt"),
    ).group_by(VideoTask.status)
    if owner_id is not None:
        stmt = stmt.where(VideoTask.owner_id == owner_id)
    if target_date is not None:
        stmt = stmt.where(VideoTask.target_date == target_date)
    if tiktok_blogger_id is not None:
        stmt = stmt.join(VideoAITemplate, VideoTask.template_id == VideoAITemplate.id)
        stmt = stmt.where(VideoAITemplate.tiktok_blogger_id == tiktok_blogger_id)
    rows = (await session.execute(stmt)).all()
    return {str(row[0]): row[1] for row in rows}


@router.get("/{task_id}", response_model=VideoTaskDetailRead)
async def get_video_task(
    task_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_query_owner_id),
    session: AsyncSession = Depends(get_db),
) -> Any:
    svc = VideoTaskService(db=session)
    item = await svc.get_task_detail(task_id, owner_id)
    data = VideoTaskDetailRead.model_validate(item["task"])
    data.account_name = item["account_name"]
    data.template_title = item["template_title"]
    return data


@router.delete("/{task_id}", status_code=status.HTTP_200_OK)
async def delete_video_task(
    task_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_query_owner_id),
    session: AsyncSession = Depends(get_db),
) -> dict:
    svc = VideoTaskService(db=session)
    await svc.delete_task(task_id, owner_id)
    return {"status": "success", "message": "删除成功"}


@router.get("/{task_id}/state", response_model=VideoTaskStateRead)
async def get_video_task_state(
    task_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_query_owner_id),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Lightweight endpoint for polling task and sub-task statuses."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from fastapi import HTTPException
    from app.models.video_task import VideoTask
    
    q = (
        select(VideoTask)
        .where(VideoTask.id == task_id)
        .options(selectinload(VideoTask.sub_tasks))
    )
    if owner_id is not None:
        q = q.where(VideoTask.owner_id == owner_id)
    task = (await session.execute(q)).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    
    return task


# ── Batch operations by date ───────────────────────────────────────────────────

import logging
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

async def _bg_upload_tasks(target_date: date, owner_id: uuid.UUID | None):
    async with SessionLocal() as session:
        svc = VideoTaskService(db=session)
        try:
            gcs_url, task_count, subtask_count = await svc.upload_tasks(target_date, owner_id)
            logger.info(f"Background upload tasks completed for {target_date}: {task_count} tasks, {subtask_count} subtasks. GCS URL: {gcs_url}")
        except Exception as e:
            logger.error(f"Background upload tasks failed for {target_date}: {e}")

async def _bg_fetch_results(target_date: date, owner_id: uuid.UUID | None):
    async with SessionLocal() as session:
        svc = VideoTaskService(db=session)
        try:
            res = await svc.fetch_results(target_date, owner_id)
            logger.info(f"Background fetch results completed for {target_date}: {res}")
        except Exception as e:
            logger.error(f"Background fetch results failed for {target_date}: {e}")

@router.post("/daily/{target_date}/upload", status_code=status.HTTP_200_OK)
async def upload_video_tasks(
    target_date: date,
    background_tasks: BackgroundTasks,
    owner_id: uuid.UUID | None = Depends(_get_query_owner_id),
) -> dict:
    background_tasks.add_task(_bg_upload_tasks, target_date, owner_id)
    return {
        "status": "success",
        "message": "后台上传任务已启动，请稍后刷新查看状态",
    }


@router.post("/daily/{target_date}/fetch-results", status_code=status.HTTP_200_OK)
async def fetch_video_task_results(
    target_date: date,
    background_tasks: BackgroundTasks,
    owner_id: uuid.UUID | None = Depends(_get_query_owner_id),
) -> dict:
    background_tasks.add_task(_bg_fetch_results, target_date, owner_id)
    return {
        "status": "success",
        "message": "后台获取结果任务已启动，请稍后刷新查看状态",
    }


# ── Sub-task endpoints ─────────────────────────────────────────────────────────

@router.patch("/subtasks/{sub_task_id}/status", response_model=VideoSubTaskRead)
async def patch_sub_task_status(
    sub_task_id: uuid.UUID,
    payload: VideoSubTaskStatusUpdate,
    owner_id: uuid.UUID | None = Depends(_get_query_owner_id),
    session: AsyncSession = Depends(get_db),
) -> Any:
    svc = VideoTaskService(db=session)
    return await svc.patch_sub_task_status(
        sub_task_id=sub_task_id,
        owner_id=owner_id,
        new_status=payload.status,
        result_video_url=payload.result_video_url,
        selected=payload.selected,
    )


@router.delete("/subtasks/{sub_task_id}", status_code=status.HTTP_200_OK)
async def delete_sub_task(
    sub_task_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_query_owner_id),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """删除待发布的子任务，若父任务无剩余有效子任务则一并删除"""
    svc = VideoTaskService(db=session)
    return await svc.delete_sub_task(sub_task_id, owner_id)


@router.post("/subtasks/{sub_task_id}/rollback", response_model=VideoSubTaskRead)
async def rollback_sub_task_status(
    sub_task_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_query_owner_id),
    session: AsyncSession = Depends(get_db),
) -> Any:
    svc = VideoTaskService(db=session)
    return await svc.rollback_sub_task_status(sub_task_id, owner_id)
