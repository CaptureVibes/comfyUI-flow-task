import uuid
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.video_publication import (
    VideoPublicationCreate,
    VideoPublicationDetailRead,
    VideoPublicationRead,
    VideoPublicationStatusUpdate,
)
from app.services.video_publication_service import VideoPublicationService

router = APIRouter()
logger = __import__("logging").getLogger("app.video_publications")


@router.post("/video-publications", response_model=VideoPublicationRead)
async def create_publication(
    data: VideoPublicationCreate,
    db: AsyncSession = Depends(get_db),
):
    """创建视频发布任务"""
    service = VideoPublicationService(db)

    # 验证子任务存在
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.video_task import VideoSubTask

    result = await db.execute(
        select(VideoSubTask)
        .where(VideoSubTask.id == data.sub_task_id)
        .options(selectinload(VideoSubTask.task))
    )
    sub_task = result.scalar_one_or_none()

    if not sub_task:
        raise HTTPException(status_code=404, detail="子任务不存在")

    if not sub_task.selected:
        raise HTTPException(status_code=400, detail="只能发布已选中的视频")

    if sub_task.status not in ("queued", "pending_publish"):
        raise HTTPException(status_code=400, detail=f"视频状态不允许发布: {sub_task.status}")

    if not sub_task.result_video_url:
        raise HTTPException(status_code=400, detail="视频尚未生成完成")

    try:
        publication = await service.create_publication(data)

        # 发布任务创建成功后，将子任务状态更新为发布中
        sub_task.status = "publishing"
        sub_task.task.status = "publishing"
        await db.commit()

        return publication
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建发布任务失败: {str(e)}")


@router.get("/video-publications/{publication_id}", response_model=VideoPublicationDetailRead)
async def get_publication(
    publication_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取发布任务详情"""
    from sqlalchemy import select
    from app.models.video_publication import VideoPublication

    result = await db.execute(
        select(VideoPublication).where(VideoPublication.id == publication_id)
    )
    publication = result.scalar_one_or_none()

    if not publication:
        raise HTTPException(status_code=404, detail="发布任务不存在")

    return publication


@router.get("/video-sub-tasks/{sub_task_id}/publications", response_model=list[VideoPublicationRead])
async def get_sub_task_publications(
    sub_task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取子任务的所有发布记录"""
    from sqlalchemy import select
    from app.models.video_task import VideoTask, VideoSubTask

    # 验证子任务存在
    result = await db.execute(
        select(VideoSubTask).where(VideoSubTask.id == sub_task_id)
    )
    sub_task = result.scalar_one_or_none()

    if not sub_task:
        raise HTTPException(status_code=404, detail="子任务不存在")

    service = VideoPublicationService(db)
    return await service.get_publications_by_sub_task(sub_task_id)


@router.post("/video-publications/{publication_id}/sync", response_model=VideoPublicationRead)
async def sync_publication_status(
    publication_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """从 Open API 同步发布任务状态"""
    from sqlalchemy import select
    from app.models.video_publication import VideoPublication

    result = await db.execute(
        select(VideoPublication).where(VideoPublication.id == publication_id)
    )
    publication = result.scalar_one_or_none()

    if not publication:
        raise HTTPException(status_code=404, detail="发布任务不存在")

    service = VideoPublicationService(db)

    try:
        return await service.sync_publication_status(publication_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"同步状态失败: {str(e)}")


@router.post("/open-api/callback/publication")
async def handle_publication_callback(
    callback_data: VideoPublicationStatusUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    接收 Open API 发布任务回调

    注意：此接口不需要认证，但需要验证签名
    """
    # TODO: 验证签名
    import logging
    logger = logging.getLogger("app.video_publications")
    logger.info(
        "Received publication callback: task_id=%s external_id=%s status=%s total=%s completed=%s failed=%s",
        callback_data.task_id,
        callback_data.external_id,
        callback_data.status,
        callback_data.total_channels,
        callback_data.completed_channels,
        callback_data.failed_channels,
    )

    service = VideoPublicationService(db)

    publication = await service.handle_callback(callback_data.dict())

    if not publication:
        import logging
        logging.getLogger("app.video_publications").warning(
            "Callback received but no matching publication found, returning 200 to avoid retry: task_id=%s external_id=%s",
            callback_data.task_id, callback_data.external_id,
        )
        return {"message": "success", "data": None}

    return {"message": "success", "data": {"publication_id": str(publication.id)}}


@router.get("/open-api/channels")
async def fetch_channels(
    platform: str = Query(..., description="平台类型: tiktok/youtube/instagram"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量，最大 100"),
    is_active: bool | None = Query(None, description="是否只获取启用的渠道"),
    db: AsyncSession = Depends(get_db),
):
    """获取 Open API 渠道列表（代理）"""
    service = VideoPublicationService(db)
    logger.info(
        "Open API channels proxy request: platform=%s page=%s page_size=%s is_active=%s",
        platform,
        page,
        page_size,
        is_active,
    )

    try:
        response = await service.fetch_channels(platform, page=page, page_size=page_size, is_active=is_active)
        data = response.get("data", {}) if isinstance(response, dict) else {}
        logger.info(
            "Open API channels proxy response: platform=%s page=%s page_size=%s code=%s total=%s items=%s message=%s",
            platform,
            page,
            page_size,
            response.get("code") if isinstance(response, dict) else None,
            data.get("total"),
            len(data.get("items") or []),
            response.get("message") if isinstance(response, dict) else None,
        )
        return response
    except (httpx.ConnectTimeout, httpx.ConnectError, httpx.TimeoutException):
        # Open API 服务不可达时返回空列表，前端降级为手动输入
        logger.warning(
            "Open API channels proxy network fallback: platform=%s page=%s page_size=%s is_active=%s",
            platform,
            page,
            page_size,
            is_active,
        )
        return {"code": 0, "message": "success", "data": {"items": [], "total": 0, "page": page, "page_size": page_size}}
    except Exception as e:
        logger.exception(
            "Open API channels proxy failed: platform=%s page=%s page_size=%s is_active=%s",
            platform,
            page,
            page_size,
            is_active,
        )
        raise HTTPException(status_code=500, detail=f"获取渠道列表失败: {str(e)}")


@router.post("/open-api/health-check")
async def open_api_health_check(
    db: AsyncSession = Depends(get_db),
):
    """检查 Open API 服务健康状态"""
    service = VideoPublicationService(db)

    try:
        return await service.open_api.health_check()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Open API 服务不可用: {str(e)}")
