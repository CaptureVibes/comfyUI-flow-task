from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenData, get_current_user
from app.db.session import get_db
from app.schemas.video_source import (
    VideoSourceCreate,
    VideoSourceListResponse,
    VideoSourceParseRequest,
    VideoSourceParseResult,
    VideoSourceRead,
    VideoSourceStatHistoryResponse,
    VideoSourceStatsResponse,
)
from app.services.video_source_service import (
    create_video_source,
    delete_video_source,
    get_stats_history,
    get_video_source_or_404,
    get_video_source_stats,
    list_video_sources,
    parse_video_url,
    trigger_download_and_upload,
)

router = APIRouter(prefix="/video-sources", tags=["video-sources"])


def _get_owner_id(current_user: TokenData = Depends(get_current_user)) -> uuid.UUID | None:
    return None if current_user.is_admin else current_user.user_id


# /stats and /parse MUST be before /{vs_id} to avoid UUID matching them
@router.get("/stats", response_model=VideoSourceStatsResponse)
async def get_stats_endpoint(
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> VideoSourceStatsResponse:
    stats = await get_video_source_stats(session, owner_id)
    return VideoSourceStatsResponse(**stats)


@router.post("/parse", response_model=VideoSourceParseResult)
async def parse_video_endpoint(
    payload: VideoSourceParseRequest,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> VideoSourceParseResult:
    """Parse a video URL via yt-dlp without saving to database.
    If source_url already exists, returns existing_id in response."""
    return await parse_video_url(payload.source_url, session=session, owner_id=owner_id)


@router.post("", response_model=VideoSourceRead, status_code=201)
async def create_video_source_endpoint(
    payload: VideoSourceCreate,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> VideoSourceRead:
    vs = await create_video_source(session, payload, owner_id)
    return VideoSourceRead.model_validate(vs)


@router.get("", response_model=VideoSourceListResponse)
async def list_video_sources_endpoint(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> VideoSourceListResponse:
    items, total = await list_video_sources(session, page=page, page_size=page_size, owner_id=owner_id)
    return VideoSourceListResponse(
        items=items,  # type: ignore[arg-type]
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{vs_id}", response_model=VideoSourceRead)
async def get_video_source_endpoint(
    vs_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> VideoSourceRead:
    vs = await get_video_source_or_404(session, vs_id, owner_id)
    return VideoSourceRead.model_validate(vs)


@router.get("/{vs_id}/stats-history", response_model=VideoSourceStatHistoryResponse)
async def get_stats_history_endpoint(
    vs_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> VideoSourceStatHistoryResponse:
    """Get historical stats for a video source."""
    items = await get_stats_history(session, vs_id, owner_id)
    return VideoSourceStatHistoryResponse(items=items)  # type: ignore[arg-type]


@router.post("/{vs_id}/download", response_model=VideoSourceRead)
async def download_video_source_endpoint(
    vs_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> VideoSourceRead:
    """Trigger background download via yt-dlp and upload to permanent storage."""
    vs = await trigger_download_and_upload(session, vs_id, owner_id)
    return VideoSourceRead.model_validate(vs)


@router.delete("/{vs_id}")
async def delete_video_source_endpoint(
    vs_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> Response:
    await delete_video_source(session, vs_id, owner_id)
    return Response(status_code=204)
