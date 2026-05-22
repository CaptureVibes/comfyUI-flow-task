from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenData, get_current_user
from app.db.session import SessionLocal, get_db
from app.models.face_photo import FacePhoto
from app.models.tag import Tag, VideoSourceTag
from app.schemas.face_photo import FacePhotoRead, TagWithFaceRead
from app.services import face_select_service

logger = logging.getLogger("app.face_library")

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
                classification_status=fp.classification_status,
                classification_error=fp.classification_error,
                classification_model=fp.classification_model,
                classified_at=fp.classified_at,
                gender=fp.gender,
                ethnicity=fp.ethnicity,
                age_estimate=fp.age_estimate,
                age_range=fp.age_range,
                beauty_percentile=fp.beauty_percentile,
                beauty_level=fp.beauty_level,
                memorability_percentile=fp.memorability_percentile,
                memorability_level=fp.memorability_level,
                notes=fp.notes,
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


_BULK_CONCURRENCY = 10


@router.post("/bulk-select")
async def bulk_select_faces(
    token: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """一键生成人脸：为所有尚未生成人脸且有关联视频的标签批量执行 AI 人脸选择。"""
    owner_id: uuid.UUID | None = None if token.is_admin else token.user_id
    owner_id_str = str(owner_id) if owner_id else None
    is_admin = token.is_admin

    # 查找所有有关联视频但没有 face_photo 的 tag
    tag_stmt = select(Tag.id).order_by(Tag.created_at.asc())
    if owner_id is not None:
        tag_stmt = tag_stmt.where(Tag.owner_id == owner_id)
    all_tag_ids = [row[0] for row in (await session.execute(tag_stmt)).fetchall()]

    if not all_tag_ids:
        return {"message": "没有标签", "queued": 0}

    # 排除已有 face_photo 的
    existing_face_stmt = select(FacePhoto.tag_id).where(FacePhoto.tag_id.in_(all_tag_ids))
    existing_face_tag_ids = set(
        row[0] for row in (await session.execute(existing_face_stmt)).fetchall()
    )

    # 排除没有关联视频的
    has_video_stmt = (
        select(VideoSourceTag.tag_id)
        .where(
            VideoSourceTag.tag_id.in_(all_tag_ids),
            VideoSourceTag.video_source_id.isnot(None),
        )
        .distinct()
    )
    has_video_tag_ids = set(
        row[0] for row in (await session.execute(has_video_stmt)).fetchall()
    )

    pending_tag_ids = [
        tid for tid in all_tag_ids
        if tid not in existing_face_tag_ids and tid in has_video_tag_ids
    ]

    if not pending_tag_ids:
        return {"message": "所有标签已有人脸或没有关联视频", "queued": 0}

    # 后台批量执行，并发控制
    sem = asyncio.Semaphore(_BULK_CONCURRENCY)

    async def _process_one(tag_id: uuid.UUID) -> None:
        async with sem:
            try:
                async with SessionLocal() as s:
                    await face_select_service.select_face_for_tag(
                        s, str(tag_id), owner_id_str, is_admin=is_admin
                    )
                logger.info("[批量人脸] tag_id=%s 成功", tag_id)
            except Exception as exc:
                logger.error("[批量人脸] tag_id=%s 失败: %s", tag_id, exc)

    async def _run_all():
        await asyncio.gather(*[_process_one(tid) for tid in pending_tag_ids])
        logger.info("[批量人脸] 全部完成，共 %d 个标签", len(pending_tag_ids))

    asyncio.create_task(_run_all())
    return {"message": f"已启动批量人脸选择，共 {len(pending_tag_ids)} 个标签", "queued": len(pending_tag_ids)}
