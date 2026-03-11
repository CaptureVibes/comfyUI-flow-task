from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenData, get_current_user
from app.db.session import get_db
from app.models.tiktok_blogger import TiktokBlogger
from app.schemas.tiktok_blogger import (
    TiktokBloggerFromUrl,
    TiktokBloggerListResponse,
    TiktokBloggerPatch,
    TiktokBloggerRead,
)
from app.schemas.video_source import VideoSourceListItem, VideoSourceListResponse
from app.services.tiktok_blogger_service import (
    create_blogger_from_url,
    delete_blogger,
    get_blogger_or_404,
    list_blogger_videos,
    list_bloggers,
    patch_blogger,
)

router = APIRouter(prefix="/tiktok-bloggers", tags=["tiktok-bloggers"])


def _get_owner_id(current_user: TokenData = Depends(get_current_user)) -> uuid.UUID | None:
    return None if current_user.is_admin else current_user.user_id


def _get_creator_id(current_user: TokenData = Depends(get_current_user)) -> uuid.UUID:
    return current_user.user_id


@router.post("", response_model=TiktokBloggerRead, status_code=201)
async def create_blogger_endpoint(
    payload: TiktokBloggerFromUrl,
    creator_id: uuid.UUID = Depends(_get_creator_id),
    session: AsyncSession = Depends(get_db),
) -> TiktokBloggerRead:
    blogger = await create_blogger_from_url(payload.profile_url, session, creator_id)
    return TiktokBloggerRead(
        **{k: getattr(blogger, k) for k in TiktokBloggerRead.model_fields if k != "video_count" and hasattr(blogger, k)},
        video_count=0,
    )


@router.get("", response_model=TiktokBloggerListResponse)
async def list_bloggers_endpoint(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    platform: str | None = Query(None),
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> TiktokBloggerListResponse:
    rows, total = await list_bloggers(
        session, page=page, page_size=page_size, owner_id=owner_id, platform=platform
    )
    items = [
        TiktokBloggerRead(
            **{k: getattr(b, k) for k in TiktokBloggerRead.model_fields if k != "video_count" and hasattr(b, k)},
            video_count=vc,
        )
        for b, vc in rows
    ]
    return TiktokBloggerListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/search", response_model=list[TiktokBloggerRead])
async def search_bloggers_endpoint(
    q: str = Query("", description="模糊搜索关键词（博主名或handle）"),
    limit: int = Query(20, ge=1, le=100),
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> list[TiktokBloggerRead]:
    """按博主名/handle 模糊搜索，用于生成页选择博主。"""
    stmt = select(TiktokBlogger).order_by(TiktokBlogger.blogger_name.asc()).limit(limit)
    if owner_id is not None:
        stmt = stmt.where(TiktokBlogger.owner_id == owner_id)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                TiktokBlogger.blogger_name.ilike(pattern),
                TiktokBlogger.blogger_handle.ilike(pattern),
            )
        )
    rows = (await session.execute(stmt)).scalars().all()
    return [
        TiktokBloggerRead(
            **{k: getattr(b, k) for k in TiktokBloggerRead.model_fields if k != "video_count" and hasattr(b, k)},
            video_count=0,
        )
        for b in rows
    ]


@router.get("/{blogger_id}", response_model=TiktokBloggerRead)
async def get_blogger_endpoint(
    blogger_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> TiktokBloggerRead:
    blogger = await get_blogger_or_404(session, blogger_id)
    return TiktokBloggerRead(
        **{k: getattr(blogger, k) for k in TiktokBloggerRead.model_fields if k != "video_count" and hasattr(blogger, k)},
        video_count=0,
    )


@router.patch("/{blogger_id}", response_model=TiktokBloggerRead)
async def patch_blogger_endpoint(
    blogger_id: uuid.UUID,
    payload: TiktokBloggerPatch,
    session: AsyncSession = Depends(get_db),
) -> TiktokBloggerRead:
    blogger = await get_blogger_or_404(session, blogger_id)
    blogger = await patch_blogger(session, blogger, payload)
    return TiktokBloggerRead(
        **{k: getattr(blogger, k) for k in TiktokBloggerRead.model_fields if k != "video_count" and hasattr(blogger, k)},
        video_count=0,
    )


@router.delete("/{blogger_id}")
async def delete_blogger_endpoint(
    blogger_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    blogger = await get_blogger_or_404(session, blogger_id)
    await delete_blogger(session, blogger)
    return Response(status_code=204)


@router.get("/{blogger_id}/videos", response_model=VideoSourceListResponse)
async def get_blogger_videos_endpoint(
    blogger_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
) -> VideoSourceListResponse:
    await get_blogger_or_404(session, blogger_id)
    items, total = await list_blogger_videos(session, blogger_id, page=page, page_size=page_size)
    return VideoSourceListResponse(
        items=[VideoSourceListItem.model_validate(v) for v in items],
        total=total,
        page=page,
        page_size=page_size,
    )
