from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
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
from app.services.gemini_service import gemini_service
from app.services.image_upload_service import image_upload_service

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
    rows = (await session.execute(stmt)).scalars().all()
    total = int(await session.scalar(total_stmt) or 0)
    return VideoAITemplateListResponse(
        items=list(rows),  # type: ignore[arg-type]
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


@router.post("/analyze-video")
async def analyze_video(
    video_source_id: uuid.UUID,
    template_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """
    Analyze video using Gemini AI and generate style images.

    This endpoint:
    1. Retrieves the video source
    2. Calls Gemini to analyze video content
    3. Generates image prompts for key shots
    4. Optionally saves results to a template if template_id is provided
    5. Returns analysis results (images are not generated yet, use /generate-images for that)
    """
    from app.services.video_source_service import get_video_source_or_404

    # Get video source
    video_source = await get_video_source_or_404(session, video_source_id, owner_id)

    try:
        # Analyze video with Gemini
        analysis = await gemini_service.analyze_video(video_source)

        prompt_description = analysis.get("description", "")
        style_analysis = analysis.get("style_analysis", "")
        key_shots = analysis.get("key_shots", [])

        # If template_id is provided, save analysis results to template
        if template_id:
            tpl = await _get_tpl_or_404(session, template_id, owner_id)
            tpl.prompt_description = prompt_description
            await session.commit()

        return {
            "success": True,
            "data": {
                "prompt_description": prompt_description,
                "style_analysis": style_analysis,
                "key_shots": key_shots,
            }
        }
    except Exception as e:
        logger.error(f"Failed to analyze video {video_source_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"视频分析失败: {str(e)}"
        ) from e


@router.post("/generate-images")
async def generate_images(
    template_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """
    Generate and upload style images for a template.

    This endpoint:
    1. Retrieves the template with analysis results
    2. Generates images based on prompts (using mock images for now)
    3. Uploads images to CDN
    4. Updates template with extracted_shots
    """
    tpl = await _get_tpl_or_404(session, template_id, owner_id)

    if not tpl.prompt_description:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先分析视频"
        )

    try:
        # Mock image URLs - in production, these would be generated by AI
        mock_image_urls = [
            "https://picsum.photos/400/600?random=1",
            "https://picsum.photos/400/600?random=2",
            "https://picsum.photos/400/600?random=3",
        ]

        # Upload images to CDN
        uploaded_shots = []
        for idx, img_url in enumerate(mock_image_urls):
            try:
                # Upload from URL
                upload_result = await image_upload_service.upload_from_url(
                    image_url=img_url,
                    filename=f"shot_{idx + 1}.png"
                )

                uploaded_shots.append({
                    "image_url": upload_result["url"],
                    "description": f"造型图 {idx + 1}",
                    "prompt": f"{tpl.prompt_description} - 镜头{idx + 1}"
                })
            except Exception as e:
                logger.error(f"Failed to upload image {idx + 1}: {e}")
                # Fallback to original URL
                uploaded_shots.append({
                    "image_url": img_url,
                    "description": f"造型图 {idx + 1}",
                    "prompt": f"{tpl.prompt_description} - 镜头{idx + 1}"
                })

        # Update template with extracted shots
        tpl.extracted_shots = uploaded_shots
        await session.commit()
        await session.refresh(tpl)

        return {
            "success": True,
            "data": {
                "extracted_shots": uploaded_shots,
                "message": f"成功生成并上传 {len(uploaded_shots)} 张造型图"
            }
        }
    except Exception as e:
        logger.error(f"Failed to generate images for template {template_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"图片生成失败: {str(e)}"
        ) from e
