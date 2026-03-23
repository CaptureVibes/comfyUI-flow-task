from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, status, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenData, get_current_user
from app.db.session import get_db
from app.models.video_ai_template import VideoAITemplate
from app.models.tag import Tag, VideoSourceTag
from app.models.video_source import VideoSource
from app.schemas.video_ai_template import VideoSourceSummary
from app.schemas.video_task import (
    VideoSubTaskNoteUpdate,
    VideoSubTaskRead,
    VideoSubTaskStatusUpdate,
    VideoTaskCreate,
    VideoTaskDetailRead,
    VideoTaskListItem,
    VideoTaskListPage,
    VideoTaskNavRead,
    VideoTaskRead,
    VideoTaskStateRead,
)
from app.services.video_task_service import VideoTaskService

router = APIRouter(prefix="/video-tasks", tags=["video-tasks"])


async def _load_template_tags_map(
    session: AsyncSession,
    template_ids: list[uuid.UUID | None],
) -> dict[uuid.UUID, list]:
    from app.schemas.video_ai_template import TagRead

    valid_ids = [tpl_id for tpl_id in template_ids if tpl_id is not None]
    tags_map: dict[uuid.UUID, list[TagRead]] = {tpl_id: [] for tpl_id in valid_ids}
    if not valid_ids:
        return tags_map

    stmt = (
        select(VideoSourceTag.video_ai_template_id, Tag)
        .join(Tag, Tag.id == VideoSourceTag.tag_id)
        .where(VideoSourceTag.video_ai_template_id.in_(valid_ids))
        .order_by(Tag.name.asc())
    )
    for tpl_id, tag in (await session.execute(stmt)).all():
        if tpl_id in tags_map:
            tags_map[tpl_id].append(TagRead.model_validate(tag))
    return tags_map


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


@router.get("", response_model=VideoTaskListPage)
async def list_video_tasks(
    target_date: date | None = Query(default=None),
    account_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    tiktok_blogger_id: uuid.UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    owner_id: uuid.UUID | None = Depends(_get_query_owner_id),
    session: AsyncSession = Depends(get_db),
) -> Any:
    svc = VideoTaskService(db=session)
    enriched, total = await svc.get_tasks_with_names(
        target_date, owner_id, account_id, status, tiktok_blogger_id,
        page=page, page_size=page_size,
    )
    tags_map = await _load_template_tags_map(session, [item["task"].template_id for item in enriched])
    items = []
    for item in enriched:
        task = item["task"]
        data = VideoTaskListItem.model_validate(task)
        data.account_name = item["account_name"]
        data.template_title = item["template_title"]
        data.sub_tasks_done = item["sub_tasks_done"]
        data.tags = tags_map.get(task.template_id, []) if task.template_id else []
        items.append(data)
    return VideoTaskListPage(items=items, total=total, page=page, page_size=page_size)


@router.get("/download-latest-published")
async def download_latest_published_videos(
    owner_id: uuid.UUID | None = Depends(_get_query_owner_id),
    session: AsyncSession = Depends(get_db),
):
    """下载每个账号最新已发布的视频，含 caption/hashtag txt，打包成 ZIP 返回。"""
    from fastapi import HTTPException
    from fastapi.responses import StreamingResponse

    svc = VideoTaskService(db=session)
    buf, filename = await svc.download_latest_published_videos(owner_id)
    if buf is None:
        raise HTTPException(status_code=404, detail="没有已发布的视频")
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
    if data.template_id:
        tags_map = await _load_template_tags_map(session, [data.template_id])
        data.tags = tags_map.get(data.template_id, [])
        tpl = await session.get(VideoAITemplate, data.template_id)
        if tpl and tpl.video_source_id:
            vs = await session.get(VideoSource, tpl.video_source_id)
            if vs:
                data.original_video = VideoSourceSummary.model_validate(vs)
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


@router.get("/{task_id}/navigation", response_model=VideoTaskNavRead)
async def get_video_task_navigation(
    task_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_query_owner_id),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Return prev/next task and prev/next blogger task for navigation without full list fetches."""
    svc = VideoTaskService(db=session)
    raw = await svc.get_task_navigation(task_id, owner_id)

    def _task_item(t):
        if t is None:
            return None
        from app.schemas.video_task import TaskNavItem
        return TaskNavItem(id=t.id, status=t.status)

    def _blogger_item(row):
        if row is None:
            return None
        from app.schemas.video_task import TaskNavItem
        t, acc = row.VideoTask, row.Account
        return TaskNavItem(id=t.id, status=t.status, account_id=acc.id, account_name=acc.account_name)

    return VideoTaskNavRead(
        position=raw["position"],
        total=raw["total"],
        selected_count=raw["selected_count"],
        prev_task=_task_item(raw["prev_task"]),
        next_task=_task_item(raw["next_task"]),
        prev_blogger_task=_blogger_item(raw["prev_blogger_task"]),
        next_blogger_task=_blogger_item(raw["next_blogger_task"]),
    )


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

@router.get("/daily/{target_date}/download-videos")
async def download_videos(
    target_date: date,
    owner_id: uuid.UUID | None = Depends(_get_query_owner_id),
    session: AsyncSession = Depends(get_db),
):
    """下载指定日期所有已选定视频，按账号分文件夹打包成 ZIP 返回。"""
    from fastapi import HTTPException
    from fastapi.responses import StreamingResponse

    svc = VideoTaskService(db=session)
    buf, filename = await svc.download_videos(target_date, owner_id)
    if buf is None:
        raise HTTPException(status_code=404, detail="该日期没有已发布的视频")
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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


@router.post("/daily/{target_date}/resume-scoring", status_code=status.HTTP_200_OK)
async def resume_video_task_scoring(
    target_date: date,
    owner_id: uuid.UUID | None = Depends(_get_query_owner_id),
    session: AsyncSession = Depends(get_db),
) -> dict:
    svc = VideoTaskService(db=session)
    result = await svc.resume_scoring_tasks(target_date, owner_id)
    return {
        "status": "success",
        "message": f"已加入 {result['queued']} 个 AI 打分任务，跳过 {result['skipped']} 个已在队列中的任务",
        **result,
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


@router.patch("/subtasks/{sub_task_id}/note", response_model=VideoSubTaskRead)
async def update_sub_task_note(
    sub_task_id: uuid.UUID,
    payload: VideoSubTaskNoteUpdate,
    owner_id: uuid.UUID | None = Depends(_get_query_owner_id),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """保存用户手动填写的备注和评分，不影响子任务状态"""
    svc = VideoTaskService(db=session)
    return await svc.update_sub_task_note(
        sub_task_id,
        owner_id,
        manual_note=payload.manual_note,
        manual_score=payload.manual_score,
        temporal_consistency=payload.temporal_consistency,
        character_integrity=payload.character_integrity,
        audio_sync=payload.audio_sync,
        dimension_scores=payload.dimension_scores,
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


@router.post("/subtasks/{sub_task_id}/enqueue", response_model=VideoSubTaskRead)
async def enqueue_sub_task(
    sub_task_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_query_owner_id),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """将子任务从 pending_publish 状态移到 queued 状态，进入发布队列"""
    svc = VideoTaskService(db=session)
    return await svc.enqueue_sub_task(sub_task_id, owner_id)


@router.post("/subtasks/{sub_task_id}/dequeue", response_model=VideoSubTaskRead)
async def dequeue_sub_task(
    sub_task_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_query_owner_id),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """将子任务从 queued 状态移回 pending_publish 状态"""
    svc = VideoTaskService(db=session)
    return await svc.dequeue_sub_task(sub_task_id, owner_id)


@router.patch("/subtasks/queue-order", status_code=status.HTTP_200_OK)
async def update_queue_order(
    payload: list[dict],
    owner_id: uuid.UUID | None = Depends(_get_query_owner_id),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """批量更新发布队列顺序，payload: [{id: uuid, queue_order: int}]"""
    from fastapi import HTTPException
    from app.models.video_task import VideoSubTask
    from sqlalchemy import select

    for item in payload:
        sub_id = uuid.UUID(item["id"])
        order = int(item["queue_order"])
        q = select(VideoSubTask).where(VideoSubTask.id == sub_id)
        if owner_id is not None:
            from app.models.video_task import VideoTask
            from sqlalchemy.orm import selectinload
            q = q.options(selectinload(VideoSubTask.task))
        sub = (await session.execute(q)).scalar_one_or_none()
        if not sub:
            raise HTTPException(status_code=404, detail=f"子任务 {sub_id} 不存在")
        if owner_id is not None and sub.task.owner_id != owner_id:
            raise HTTPException(status_code=403, detail="无权操作")
        sub.queue_order = order

    await session.commit()
    return {"status": "ok"}
