from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenData, get_current_user
from app.db.session import get_db
from app.models.face_photo import FacePhoto
from app.models.tag import Tag, VideoSourceTag
from app.schemas.face_photo import FacePhotoRead, TagWithFaceRead
from app.services import face_select_service

router = APIRouter(prefix="/face-library", tags=["face-library"])


@router.get("", response_model=list[TagWithFaceRead])
async def list_tags_with_faces(
    token: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[TagWithFaceRead]:
    """列出当前用户的所有标签，附带人脸照片（如有）和视频数量。"""
    owner_id: uuid.UUID | None = None if token.is_admin else token.user_id

    # 查询 tags
    stmt = select(Tag).order_by(Tag.created_at.asc())
    if owner_id is not None:
        stmt = stmt.where(Tag.owner_id == owner_id)
    tags = (await session.execute(stmt)).scalars().all()

    if not tags:
        return []

    tag_ids = [t.id for t in tags]

    # 查询每个 tag 的视频数量
    count_stmt = (
        select(VideoSourceTag.tag_id, func.count(VideoSourceTag.id).label("cnt"))
        .where(
            VideoSourceTag.tag_id.in_(tag_ids),
            VideoSourceTag.video_source_id.isnot(None),
        )
        .group_by(VideoSourceTag.tag_id)
    )
    count_rows = (await session.execute(count_stmt)).all()
    video_count_map: dict[uuid.UUID, int] = {row.tag_id: row.cnt for row in count_rows}

    # 查询每个 tag 的人脸照片（每个 tag 最多一条）
    face_stmt = select(FacePhoto).where(FacePhoto.tag_id.in_(tag_ids))
    face_rows = (await session.execute(face_stmt)).scalars().all()
    face_map: dict[uuid.UUID, FacePhoto] = {fp.tag_id: fp for fp in face_rows}

    result: list[TagWithFaceRead] = []
    for tag in tags:
        fp = face_map.get(tag.id)
        face_photo_read = (
            FacePhotoRead(
                id=str(fp.id),
                tag_id=str(fp.tag_id),
                face_photo_url=fp.face_photo_url,
                frame_index=fp.frame_index,
                created_at=fp.created_at,
            )
            if fp else None
        )
        result.append(
            TagWithFaceRead(
                id=str(tag.id),
                name=tag.name,
                color=tag.color,
                owner_id=str(tag.owner_id) if tag.owner_id else None,
                video_count=video_count_map.get(tag.id, 0),
                face_photo=face_photo_read,
            )
        )

    return result


@router.post("/tags/{tag_id}/select-face")
async def trigger_face_selection(
    tag_id: uuid.UUID,
    token: TokenData = Depends(get_current_user),
) -> dict:
    """触发 AI 人脸选择（异步后台执行）。"""
    import asyncio
    from app.db.session import SessionLocal

    owner_id = str(token.user_id)
    is_admin = token.is_admin

    async def _run():
        try:
            async with SessionLocal() as session:
                await face_select_service.select_face_for_tag(session, str(tag_id), owner_id, is_admin=is_admin)
        except Exception as exc:
            import logging
            logging.getLogger("app.face_select").error("人脸选择后台任务失败 tag_id=%s: %s", tag_id, exc)

    asyncio.create_task(_run())
    return {"status": "submitted", "tag_id": str(tag_id)}
