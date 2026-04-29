import csv
import io
import uuid
from datetime import date
from urllib.parse import quote
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import TokenData, get_current_user
from app.db.session import get_db
from app.schemas.video_publication import (
    VideoPublicationCreate,
    VideoPublicationDetailRead,
    VideoPublicationRead,
    VideoPublicationStatsListResponse,
    VideoPublicationStatsQuery,
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
        return publication
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建发布任务失败: {str(e)}")


@router.get("/video-publications/stats", response_model=VideoPublicationStatsListResponse)
async def get_publication_stats(
    platform: str | None = Query(None, description="平台类型: tiktok/youtube/instagram"),
    account_id: uuid.UUID | None = Query(None, description="账号 ID"),
    date_from: date | None = Query(None, description="发布时间起始日期"),
    date_to: date | None = Query(None, description="发布时间结束日期"),
    keyword: str | None = Query(None, description="标题/账号/渠道/平台链接关键字"),
    sort_by: str = Query("published_at", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向: asc/desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取数据统计页已发布视频列表。"""
    query = VideoPublicationStatsQuery(
        platform=platform,
        account_id=account_id,
        date_from=date_from,
        date_to=date_to,
        keyword=keyword,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    owner_id = None if current_user.is_admin else current_user.user_id
    service = VideoPublicationService(db)
    items, total = await service.get_publication_stats_page(query, owner_id=owner_id)
    return VideoPublicationStatsListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/video-publications/stats/export")
async def export_publication_stats(
    platform: str | None = Query(None),
    account_id: uuid.UUID | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    keyword: str | None = Query(None),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """导出数据统计 CSV，按博主×日期透视表格式。"""
    query = VideoPublicationStatsQuery(
        platform=platform,
        account_id=account_id,
        date_from=date_from,
        date_to=date_to,
        keyword=keyword,
    )
    owner_id = None if current_user.is_admin else current_user.user_id
    service = VideoPublicationService(db)
    items = await service.get_publication_stats_all(query, owner_id=owner_id)

    # 收集所有出现的日期（列），升序
    date_set: set[str] = set()
    for item in items:
        dt = item.published_at or item.created_at
        if dt:
            date_set.add(dt.strftime("%Y-%m-%d"))
    dates = sorted(date_set, reverse=True)

    # 收集每个 account_id 绑定的平台（优先从 social_bindings 提取，拼完整主页 URL）
    _platform_base = {
        "youtube": "https://www.youtube.com/",
        "tiktok": "https://www.tiktok.com/",
        "instagram": "https://www.instagram.com/",
    }
    account_platforms: dict[uuid.UUID | None, str] = {}
    account_channel_names: dict[uuid.UUID | None, str] = {}
    seen_ids: set[uuid.UUID | None] = set()
    for item in items:
        aid = item.account_id
        if aid in seen_ids:
            continue
        seen_ids.add(aid)
        # 优先从 account.social_bindings 提取，生成完整 URL 和 channel_name
        url_parts: list[str] = []
        channel_name_parts: list[str] = []
        for binding in item.social_bindings or []:
            if not isinstance(binding, dict):
                continue
            p = str(binding.get("platform") or "").lower()
            username = str(binding.get("username") or "").strip()
            channel_name = str(binding.get("channel_name") or "").strip()
            if not p:
                continue
            base = _platform_base.get(p)
            if base and username:
                url_parts.append(f"{base}{username}")
            elif base:
                url_parts.append(base.rstrip("/"))
            if channel_name:
                channel_name_parts.append(channel_name)
        # 兜底：从 metrics_channels 和 channels_status 补充平台名
        if not url_parts:
            platforms_set: set[str] = set()
            for ch in item.metrics_channels:
                p = str(ch.platform or "").lower()
                if p:
                    platforms_set.add(p)
            for ch in item.channels_status or []:
                p = str(ch.platform or "").lower()
                if p:
                    platforms_set.add(p)
            url_parts = [_platform_base.get(p, p).rstrip("/") for p in sorted(platforms_set)]
        account_platforms[aid] = "\n".join(url_parts)
        account_channel_names[aid] = "\n".join(channel_name_parts)

    # 按账号名分组：{ name -> { account_type, platforms, date -> [(views, likes)] } }
    blogger_map: dict[str, dict] = {}
    for item in items:
        name = item.account_name or "未知账号"
        if name not in blogger_map:
            _type_map = {"persona": "人设号", "shared": "共享号", "exclusive": "独享号"}
            account_type = _type_map.get(item.account_type or "", "共享号")
            platforms = account_platforms.get(item.account_id, "")
            channel_names = account_channel_names.get(item.account_id, "")
            blogger_map[name] = {"account_type": account_type, "platforms": platforms, "channel_names": channel_names, "dates": {}}
        dt = item.published_at or item.created_at
        if not dt:
            continue
        day = dt.strftime("%Y-%m-%d")
        blogger_map[name]["dates"].setdefault(day, []).append(
            (item.total_views or 0, item.total_likes or 0)
        )

    # 构建 CSV（UTF-8 BOM，Excel 直接识别中文）
    buf = io.StringIO()
    buf.write("\ufeff")  # BOM
    writer = csv.writer(buf)
    writer.writerow(["博主名称", "账号类型", "绑定平台", "频道名称", *dates])
    for name, info in blogger_map.items():
        row = [name, info["account_type"], info["platforms"], info["channel_names"]]
        for day in dates:
            entries = info["dates"].get(day, [])
            row.append("\n".join(f"▶{v} ♥{l}" for v, l in entries))
        writer.writerow(row)

    filename = "数据统计"
    if date_from:
        filename += f"_{date_from}"
    if date_to and date_to != date_from:
        filename += f"_{date_to}"
    filename += ".csv"

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.post("/video-publications/sync-metrics")
async def sync_publication_metrics(
    background_tasks: BackgroundTasks,
    platform: str | None = Query(None),
    account_id: uuid.UUID | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """先查出待同步数量立即返回，后台执行指标同步"""
    from sqlalchemy import select, func
    from app.models.video_task import VideoSubTask, VideoTask
    from app.db.session import SessionLocal

    query = VideoPublicationStatsQuery(
        platform=platform,
        account_id=account_id,
        date_from=date_from,
        date_to=date_to,
    )
    owner_id = None if current_user.is_admin else current_user.user_id

    # 先查数量
    from datetime import date as date_type
    from app.models.video_publication import VideoPublication
    stmt = (
        select(func.count())
        .select_from(VideoPublication)
        .join(VideoSubTask, VideoSubTask.id == VideoPublication.sub_task_id)
        .join(VideoTask, VideoTask.id == VideoSubTask.task_id)
        .where(VideoPublication.status.in_(["completed", "partial"]))
        .where(VideoPublication.open_api_task_id.isnot(None))
    )
    if owner_id is not None:
        stmt = stmt.where(VideoTask.owner_id == owner_id)
    if query.account_id is not None:
        stmt = stmt.where(VideoTask.account_id == query.account_id)
    if query.date_from is not None:
        from datetime import datetime, timezone
        stmt = stmt.where(
            VideoPublication.completed_at >= datetime.combine(query.date_from, datetime.min.time(), tzinfo=timezone.utc)
        )
    if query.date_to is not None:
        from datetime import datetime, timezone
        next_day = date_type.fromordinal(query.date_to.toordinal() + 1)
        stmt = stmt.where(
            VideoPublication.completed_at < datetime.combine(next_day, datetime.min.time(), tzinfo=timezone.utc)
        )
    total = (await db.execute(stmt)).scalar() or 0

    async def _run():
        try:
            async with SessionLocal() as bg_db:
                service = VideoPublicationService(bg_db)
                result = await service.sync_metrics_for_stats_page(query, owner_id=owner_id)
                logger.info("sync-metrics background done: %s", result)
        except Exception:
            logger.exception("sync-metrics background failed")

    background_tasks.add_task(_run)
    return {"total": total, "message": f"后台同步 {total} 条视频数据中"}


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


@router.post("/video-publications/{publication_id}/retry", response_model=VideoPublicationRead)
async def retry_publication(
    publication_id: uuid.UUID,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """用上次的发布参数直接重新发布（sub_task 必须处于 publish_failed 状态）"""
    owner_id = None if current_user.is_admin else current_user.user_id
    service = VideoPublicationService(db)
    try:
        return await service.retry_publication(publication_id, owner_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重试发布失败: {str(e)}")


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


@router.post("/video-publications/sync-account-snapshots")
async def sync_account_snapshots(
    background_tasks: BackgroundTasks,
    account_id: uuid.UUID | None = Query(None, description="指定账号 ID，不传则计算所有账号"),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """先查出待计算账号数量立即返回，后台执行 performance_snapshot 计算"""
    from sqlalchemy import select, func
    from app.models.account import Account
    from app.db.session import SessionLocal
    from app.services.publication_metrics_scheduler import sync_account_performance_snapshots

    stmt = select(func.count()).select_from(Account)
    if account_id is not None:
        stmt = stmt.where(Account.id == account_id)
    total = (await db.execute(stmt)).scalar() or 0

    async def _run():
        try:
            async with SessionLocal() as bg_db:
                result = await sync_account_performance_snapshots(bg_db, account_id=account_id)
                logger.info("sync-account-snapshots background done: %s", result)
        except Exception:
            logger.exception("sync-account-snapshots background failed")

    background_tasks.add_task(_run)
    return {"total": total, "message": f"后台同步 {total} 个博主数据中"}


@router.get("/channels")
async def fetch_channels_unified(
    platform: str = Query(..., description="平台类型: tiktok/youtube/instagram"),
    channel_source: str = Query(..., description="频道来源: openapi（内部）| ext_pub（外部）"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=200, description="每页数量，最大 200"),
    is_active: bool | None = Query(None, description="是否只获取启用的渠道（仅内部频道有效）"),
    account_id: uuid.UUID | None = Query(None, description="当前编辑中的账号 ID，用于保留它自己已绑定的频道"),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """统一频道查询接口。

    通过 channel_source 参数区分内部（openapi）和外部（ext_pub）频道。
    两侧均过滤当前用户已被其他账号占用的频道，返回归一化结构：
    { channel_id, channel_name, username, platform, channel_source, avatar_url }
    """
    if channel_source not in ("openapi", "ext_pub"):
        raise HTTPException(status_code=422, detail="channel_source 必须为 openapi 或 ext_pub")

    service = VideoPublicationService(db)
    usage_types = settings.open_api_channel_usage_types_list or None if channel_source == "openapi" else None

    logger.info(
        "channels unified request: platform=%s source=%s page=%s page_size=%s account_id=%s user_id=%s",
        platform, channel_source, page, page_size, account_id, current_user.user_id,
    )
    try:
        response = await service.fetch_channels_unified(
            platform=platform,
            channel_source=channel_source,
            owner_id=current_user.user_id,
            page=page,
            page_size=page_size,
            is_active=is_active,
            current_account_id=account_id,
            usage_types=usage_types,
        )
        data = response.get("data", {}) if isinstance(response, dict) else {}
        logger.info(
            "channels unified response: platform=%s source=%s total=%s returned=%s",
            platform, channel_source, data.get("total"), len(data.get("items") or []),
        )
        return response
    except (httpx.ConnectTimeout, httpx.ConnectError, httpx.TimeoutException):
        logger.warning("channels unified network fallback: platform=%s source=%s", platform, channel_source)
        return {"code": 0, "message": "success", "data": {"items": [], "total": 0, "page": page, "page_size": page_size}}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("channels unified failed: platform=%s source=%s", platform, channel_source)
        raise HTTPException(status_code=500, detail=f"获取频道列表失败: {str(e)}")


@router.get("/open-api/channels")
async def fetch_channels(
    platform: str = Query(..., description="平台类型: tiktok/youtube/instagram"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量，最大 100"),
    is_active: bool | None = Query(None, description="是否只获取启用的渠道"),
    account_id: uuid.UUID | None = Query(None, description="当前编辑中的账号 ID，用于保留它自己已绑定的频道"),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取 Open API 渠道列表（代理，兼容旧版）"""
    service = VideoPublicationService(db)
    try:
        usage_types = settings.open_api_channel_usage_types_list or None
        response = await service.fetch_channels_filtered(
            platform,
            owner_id=current_user.user_id,
            page=page,
            page_size=page_size,
            is_active=is_active,
            current_account_id=account_id,
            usage_types=usage_types,
        )
        return response
    except (httpx.ConnectTimeout, httpx.ConnectError, httpx.TimeoutException):
        return {"code": 0, "message": "success", "data": {"items": [], "total": 0, "page": page, "page_size": page_size}}
    except Exception as e:
        logger.exception("Open API channels proxy failed: platform=%s", platform)
        raise HTTPException(status_code=500, detail=f"获取渠道列表失败: {str(e)}")


@router.get("/ext-pub/platform-accounts")
async def fetch_ext_pub_platform_accounts(
    platform: str | None = Query(None, description="平台过滤：tiktok/youtube/instagram"),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取外部发布 API 的平台账号列表（代理，兼容旧版）"""
    service = VideoPublicationService(db)
    try:
        result = await service.ext_pub.fetch_platform_accounts(platform=platform)
        return result
    except (httpx.ConnectTimeout, httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError):
        logger.warning("ExtPubAPI platform-accounts proxy fallback: platform=%s", platform)
        return {"code": 200, "message": "Success", "data": {"items": [], "total": 0}}
    except Exception:
        logger.exception("ExtPubAPI platform-accounts proxy failed")
        return {"code": 200, "message": "Success", "data": {"items": [], "total": 0}}


@router.get("/open-api/upload/metrics")
async def get_upload_metrics(
    task_id: str | None = Query(None, description="Open API 任务 ID"),
    external_id: str | None = Query(None, description="外部系统 ID"),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询上传任务各渠道视频指标（代理到 Open API）"""
    if not task_id and not external_id:
        raise HTTPException(status_code=400, detail="task_id 和 external_id 至少提供一个")

    service = VideoPublicationService(db)
    try:
        return await service.open_api.fetch_upload_metrics(task_id=task_id, external_id=external_id)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Open API 返回错误: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询指标失败: {str(e)}")


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
