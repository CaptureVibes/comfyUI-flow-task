from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenData, get_current_user
from app.db.session import get_db
from app.models.enums import VideoAIProcessStatus
from app.models.video_ai_template import VideoAITemplate
from app.models.video_source import VideoSource
from app.schemas.video_ai_template import (
    VideoAITemplateCreate,
    VideoAITemplateListResponse,
    VideoAITemplatePatch,
    VideoAITemplateRead,
    VideoSourceSummary,
)
from app.services.video_ai_service import (
    enqueue_template,
    get_template_state,
    pause_template,
    resume_template,
)

router = APIRouter(prefix="/video-ai-templates", tags=["video-ai-templates"])


def _get_owner_id(current_user: TokenData = Depends(get_current_user)) -> uuid.UUID | None:
    return None if current_user.is_admin else current_user.user_id


async def _get_tpl_or_404(
    session: AsyncSession,
    tpl_id: uuid.UUID,
    owner_id: uuid.UUID | None = None,
) -> VideoAITemplate:
    tpl = await session.scalar(select(VideoAITemplate).where(VideoAITemplate.id == tpl_id))
    if not tpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在")
    if owner_id is not None and tpl.owner_id != owner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在")
    return tpl


async def _to_read(session: AsyncSession, tpl: VideoAITemplate) -> VideoAITemplateRead:
    video_source = None
    if tpl.video_source_id:
        vs = await session.get(VideoSource, tpl.video_source_id)
        if vs:
            video_source = VideoSourceSummary.model_validate(vs)
    return VideoAITemplateRead(
        id=tpl.id,
        owner_id=tpl.owner_id,
        title=tpl.title,
        description=tpl.description,
        video_source_id=tpl.video_source_id,
        video_source=video_source,
        process_status=tpl.process_status,
        process_error=tpl.process_error,
        prompt_description=tpl.prompt_description,
        extracted_shots=tpl.extracted_shots,
        extra=tpl.extra,
        created_at=tpl.created_at,
        updated_at=tpl.updated_at,
    )


@router.post("", response_model=VideoAITemplateRead, status_code=201)
async def create_template(
    payload: VideoAITemplateCreate,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> VideoAITemplateRead:
    tpl = VideoAITemplate(
        owner_id=owner_id,
        title=payload.title,
        description=payload.description,
        video_source_id=payload.video_source_id,
        process_status=VideoAIProcessStatus.pending,
        prompt_description=payload.prompt_description,
        extracted_shots=payload.extracted_shots,
        extra=payload.extra,
    )
    session.add(tpl)
    await session.commit()
    await session.refresh(tpl)
    return await _to_read(session, tpl)


@router.get("", response_model=VideoAITemplateListResponse)
async def list_templates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    video_source_id: uuid.UUID | None = Query(None),
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> VideoAITemplateListResponse:
    from sqlalchemy import func

    stmt = (
        select(VideoAITemplate)
        .order_by(VideoAITemplate.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    total_stmt = select(func.count(VideoAITemplate.id))
    if owner_id is not None:
        stmt = stmt.where(VideoAITemplate.owner_id == owner_id)
        total_stmt = total_stmt.where(VideoAITemplate.owner_id == owner_id)
    if video_source_id is not None:
        stmt = stmt.where(VideoAITemplate.video_source_id == video_source_id)
        total_stmt = total_stmt.where(VideoAITemplate.video_source_id == video_source_id)
    rows = (await session.execute(stmt)).scalars().all()
    total = int(await session.scalar(total_stmt) or 0)
    items_read = []
    for r in rows:
        items_read.append(await _to_read(session, r))

    return VideoAITemplateListResponse(
        items=items_read,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{tpl_id}", response_model=VideoAITemplateRead)
async def get_template(
    tpl_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> VideoAITemplateRead:
    tpl = await _get_tpl_or_404(session, tpl_id, owner_id)
    return await _to_read(session, tpl)


@router.patch("/{tpl_id}", response_model=VideoAITemplateRead)
async def patch_template(
    tpl_id: uuid.UUID,
    payload: VideoAITemplatePatch,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> VideoAITemplateRead:
    tpl = await _get_tpl_or_404(session, tpl_id, owner_id)
    if payload.title is not None:
        tpl.title = payload.title
    if payload.description is not None:
        tpl.description = payload.description
    if payload.video_source_id is not None:
        tpl.video_source_id = payload.video_source_id
    if payload.prompt_description is not None:
        tpl.prompt_description = payload.prompt_description
    if payload.extracted_shots is not None:
        tpl.extracted_shots = payload.extracted_shots
    if payload.extra is not None:
        tpl.extra = payload.extra
    await session.commit()
    await session.refresh(tpl)
    return await _to_read(session, tpl)


@router.delete("/{tpl_id}")
async def delete_template(
    tpl_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> Response:
    tpl = await _get_tpl_or_404(session, tpl_id, owner_id)
    from sqlalchemy import delete as sa_delete
    await session.execute(sa_delete(VideoAITemplate).where(VideoAITemplate.id == tpl.id))
    await session.commit()
    return Response(status_code=204)


@router.post("/{tpl_id}/start", response_model=VideoAITemplateRead)
async def start_template(
    tpl_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> VideoAITemplateRead:
    tpl = await _get_tpl_or_404(session, tpl_id, owner_id)
    await enqueue_template(str(tpl.id))
    await session.refresh(tpl)
    return await _to_read(session, tpl)


@router.post("/{tpl_id}/pause", response_model=VideoAITemplateRead)
async def pause_template_endpoint(
    tpl_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> VideoAITemplateRead:
    tpl = await _get_tpl_or_404(session, tpl_id, owner_id)
    await pause_template(str(tpl.id))
    await session.refresh(tpl)
    return await _to_read(session, tpl)


@router.post("/{tpl_id}/resume", response_model=VideoAITemplateRead)
async def resume_template_endpoint(
    tpl_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> VideoAITemplateRead:
    tpl = await _get_tpl_or_404(session, tpl_id, owner_id)
    await resume_template(str(tpl.id))
    await session.refresh(tpl)
    return await _to_read(session, tpl)


@router.get("/{tpl_id}/state")
async def get_template_state_endpoint(
    tpl_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> dict:
    tpl = await _get_tpl_or_404(session, tpl_id, owner_id)
    state = get_template_state(str(tpl.id))
    if state is None:
        # Return DB state
        return {
            "template_id": str(tpl.id),
            "status": tpl.process_status.value,
            "error_message": tpl.process_error or "",
            "prompt_description": tpl.prompt_description or "",
            "extracted_shots": tpl.extracted_shots or [],
        }
    return state


@router.post("/{tpl_id}/upload-shot")
async def upload_shot_image(
    tpl_id: uuid.UUID,
    file: UploadFile = File(...),
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.upload_service import UpstreamImageUploadService
    tpl = await _get_tpl_or_404(session, tpl_id, owner_id)
    content = await file.read()
    content_type = file.content_type or "image/png"
    svc = UpstreamImageUploadService()
    result = await svc.upload_image(content, content_type, file.filename)
    return {"url": result.url}


