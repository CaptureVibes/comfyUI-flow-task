from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenData, get_current_user
from app.db.session import SessionLocal, get_db
from app.schemas.settings import (
    CandidateBatchAIReviewRequest,
    CandidateBatchImportRequest,
    CandidateSearchPayload,
    CandidateVideoItem,
    CandidateVideoListResponse,
)
from app.services import candidate_service
from app.services.candidate_service import delete_candidate_video, list_candidate_videos

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.post("/search")
async def trigger_candidate_search(
    payload: CandidateSearchPayload,
    token: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """
    触发候选库搜索（后台任务）。
    立即返回 202，搜索在后台异步执行。
    """
    kid: uuid.UUID | None = None
    if payload.keyword_id:
        try:
            kid = uuid.UUID(payload.keyword_id)
        except ValueError:
            kid = None

    # 不管是否 admin，都用 user_id 作为 owner_id 存入候选库
    owner_id: uuid.UUID | None = None
    if token.user_id:
        owner_id = uuid.UUID(str(token.user_id))

    # 后台执行，不等待结果（后台任务自己管理 session 生命周期）
    async def _bg_search(keyword_text: str, keyword_id: uuid.UUID | None, owner_id: uuid.UUID | None) -> None:
        async with SessionLocal() as bg_session:
            try:
                await candidate_service.run_candidate_search(
                    session=bg_session,
                    keyword_text=keyword_text,
                    keyword_id=keyword_id,
                    owner_id=owner_id,
                )
            except Exception as exc:
                logger.exception("【候选库API】后台搜索任务异常: %s", exc)

    asyncio.create_task(_bg_search(payload.keyword_text, kid, owner_id))

    logger.info("【候选库API】已触发搜索任务 keyword=%s owner=%s", payload.keyword_text, owner_id)
    return {"message": "搜索任务已启动"}


@router.get("", response_model=CandidateVideoListResponse)
async def get_candidates(
    keyword_id: str | None = Query(None),
    template_type: str | None = Query(None, description="shared 或 exclusive"),
    imported: bool | None = Query(None, description="true=已导入库, false=候选库, 不传=全部"),
    status: str | None = Query(None, description="按状态筛选: pending/ai_reviewing/ai_passed/ai_failed/importing/imported/import_failed"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    token: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CandidateVideoListResponse:
    owner_id: uuid.UUID | None = None
    if not token.is_admin and token.user_id:
        owner_id = uuid.UUID(str(token.user_id))

    kid: uuid.UUID | None = None
    if keyword_id:
        try:
            kid = uuid.UUID(keyword_id)
        except ValueError:
            kid = None

    result = await list_candidate_videos(
        session,
        owner_id=owner_id,
        keyword_id=kid,
        template_type=template_type,
        imported=imported,
        status=status,
        page=page,
        page_size=page_size,
    )

    items = [
        CandidateVideoItem(
            id=str(row.id),
            keyword_id=str(row.keyword_id) if row.keyword_id else None,
            keyword_text=row.keyword_text,
            template_type=row.template_type,
            blogger_unique_id=row.blogger_unique_id,
            blogger_nickname=row.blogger_nickname,
            blogger_follower_count=row.blogger_follower_count,
            video_id=row.video_id,
            video_url=row.video_url,
            video_title=row.video_title,
            duration=row.duration,
            cover_url=row.cover_url,
            cdn_cover_url=row.cdn_cover_url,
            play_count=row.play_count,
            like_count=row.like_count,
            status=str(row.status.value if hasattr(row.status, 'value') else row.status),
            ai_reviewed=row.ai_reviewed,
            ai_error=row.ai_error,
            created_at=row.created_at,
        )
        for row in result["items"]
    ]

    return CandidateVideoListResponse(
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        items=items,
    )


@router.delete("/{video_id}")
async def remove_candidate_video(
    video_id: uuid.UUID,
    token: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Response:
    owner_id: uuid.UUID | None = None
    if not token.is_admin and token.user_id:
        owner_id = uuid.UUID(str(token.user_id))

    ok = await delete_candidate_video(session, video_id, owner_id)
    if not ok:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="候选视频不存在或无权限删除")
    return Response(status_code=204)


@router.post("/ai-review-all")
async def bulk_ai_review(
    template_type: str | None = Query(None, description="shared 或 exclusive，不传则全部"),
    token: TokenData = Depends(get_current_user),
):
    """全量 AI 审核：将所有 pending/ai_failed 的候选视频加入后台审核队列（立即返回）"""
    owner_id = None if token.is_admin else str(token.user_id)
    result = await candidate_service.trigger_bulk_ai_review(template_type=template_type, owner_id=owner_id)
    return {"message": f"已加入审核队列，共 {result['queued']} 条视频"}


@router.post("/ai-review")
async def batch_ai_review(
    body: CandidateBatchAIReviewRequest,
    token: TokenData = Depends(get_current_user),
):
    """手动批量 AI 审核候选视频（后台异步执行，立即返回）"""
    owner_id = None if token.is_admin else str(token.user_id)
    ids = body.ids

    async def _bg():
        async with SessionLocal() as bg_session:
            try:
                await candidate_service.ai_review_candidates_by_ids(bg_session, ids, owner_id)
            except Exception as exc:
                logger.exception("【候选库】后台 AI 审核异常: %s", exc)

    asyncio.create_task(_bg())
    return {"message": f"AI 审核已启动，共 {len(ids)} 条视频"}


@router.post("/import")
async def batch_import(
    body: CandidateBatchImportRequest,
    token: TokenData = Depends(get_current_user),
):
    """手动批量导入 ai_passed 的候选视频到视频库（后台异步执行，立即返回）"""
    owner_id = None if token.is_admin else str(token.user_id)
    ids = body.ids

    async def _bg():
        async with SessionLocal() as bg_session:
            try:
                await candidate_service.import_candidates_by_ids(bg_session, ids, owner_id)
            except Exception as exc:
                logger.exception("【候选库】后台导入异常: %s", exc)

    asyncio.create_task(_bg())
    return {"message": f"导入已启动，共 {len(ids)} 条视频"}
