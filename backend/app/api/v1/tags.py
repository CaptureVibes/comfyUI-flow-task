from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenData, get_current_user
from app.db.session import get_db
from app.models.tag import Tag, VideoSourceTag
from app.schemas.video_source import TagCreate, TagRead

router = APIRouter(prefix="/tags", tags=["tags"])


def _owner_id(current_user: TokenData = Depends(get_current_user)) -> uuid.UUID | None:
    """Admin gets None (global scope), regular user gets their own id."""
    return None if current_user.is_admin else current_user.user_id


class VideoSourceTagRead(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID | None
    video_source_id: uuid.UUID | None
    video_ai_template_id: uuid.UUID | None
    tag_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class TagAttachBody(BaseModel):
    tag_id: uuid.UUID


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Tag CRUD ──────────────────────────────────────────────────────────────────

@router.get("", response_model=list[TagRead])
async def list_tags(
    owner_id: uuid.UUID | None = Depends(_owner_id),
    session: AsyncSession = Depends(get_db),
) -> list[TagRead]:
    """List tags visible to the current user."""
    stmt = select(Tag).order_by(Tag.created_at.asc())
    if owner_id is not None:
        stmt = stmt.where(Tag.owner_id == owner_id)
    rows = (await session.execute(stmt)).scalars().all()
    return [TagRead.model_validate(r) for r in rows]


@router.post("", response_model=TagRead, status_code=201)
async def create_tag(
    payload: TagCreate,
    current_user: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TagRead:
    tag = Tag(
        owner_id=current_user.user_id,
        name=payload.name,
        color=payload.color,
    )
    session.add(tag)
    await session.commit()
    await session.refresh(tag)
    return TagRead.model_validate(tag)


class TagUpdate(BaseModel):
    name: str | None = None
    color: str | None = None


@router.patch("/{tag_id}", response_model=TagRead)
async def update_tag(
    tag_id: uuid.UUID,
    payload: TagUpdate,
    owner_id: uuid.UUID | None = Depends(_owner_id),
    session: AsyncSession = Depends(get_db),
) -> TagRead:
    stmt = select(Tag).where(Tag.id == tag_id)
    if owner_id is not None:
        stmt = stmt.where(Tag.owner_id == owner_id)
    tag = await session.scalar(stmt)
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")
    if payload.name is not None:
        tag.name = payload.name
    if payload.color is not None:
        tag.color = payload.color
    await session.commit()
    await session.refresh(tag)
    return TagRead.model_validate(tag)


@router.delete("/{tag_id}", status_code=204)
async def delete_tag(
    tag_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_owner_id),
    session: AsyncSession = Depends(get_db),
) -> Response:
    stmt = select(Tag).where(Tag.id == tag_id)
    if owner_id is not None:
        stmt = stmt.where(Tag.owner_id == owner_id)
    tag = await session.scalar(stmt)
    if tag:
        await session.delete(tag)
        await session.commit()
    return Response(status_code=204)


class TagVideoCountBody(BaseModel):
    tag_ids: list[uuid.UUID]


class TagVideoCountResult(BaseModel):
    total_video_count: int


@router.post("/video-count", response_model=TagVideoCountResult)
async def get_tags_video_count(
    payload: TagVideoCountBody,
    owner_id: uuid.UUID | None = Depends(_owner_id),
    session: AsyncSession = Depends(get_db),
) -> TagVideoCountResult:
    """批量查询多个标签下关联的视频总数。"""
    if not payload.tag_ids:
        return TagVideoCountResult(total_video_count=0)

    from sqlalchemy import func

    stmt = select(func.count(func.distinct(VideoSourceTag.video_source_id))).where(
        VideoSourceTag.tag_id.in_(payload.tag_ids)
    )
    count = await session.scalar(stmt) or 0
    return TagVideoCountResult(total_video_count=count)


# ── 视频标签关联 ───────────────────────────────────────────────────────────────

@router.get("/video-sources/{vs_id}/tags", response_model=list[TagRead])
async def get_video_source_tags(
    vs_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[TagRead]:
    """获取某视频的所有标签。"""
    stmt = (
        select(Tag)
        .join(VideoSourceTag, VideoSourceTag.tag_id == Tag.id)
        .where(VideoSourceTag.video_source_id == vs_id)
        .order_by(Tag.name.asc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [TagRead.model_validate(r) for r in rows]


@router.post("/video-sources/{vs_id}/tags", response_model=VideoSourceTagRead, status_code=201)
async def attach_tag_to_video_source(
    vs_id: uuid.UUID,
    body: TagAttachBody,
    current_user: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> VideoSourceTagRead:
    """给视频打标签。"""
    tag = await session.get(Tag, body.tag_id)
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标签不存在")

    existing = await session.scalar(
        select(VideoSourceTag)
        .where(VideoSourceTag.video_source_id == vs_id)
        .where(VideoSourceTag.tag_id == body.tag_id)
    )
    if existing:
        return VideoSourceTagRead.model_validate(existing)

    entry = VideoSourceTag(
        owner_id=current_user.user_id,
        video_source_id=vs_id,
        tag_id=body.tag_id,
        created_at=_utcnow(),
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return VideoSourceTagRead.model_validate(entry)


@router.delete("/video-sources/{vs_id}/tags/{tag_id}", status_code=204)
async def detach_tag_from_video_source(
    vs_id: uuid.UUID,
    tag_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    """移除视频的某个标签。"""
    entry = await session.scalar(
        select(VideoSourceTag)
        .where(VideoSourceTag.video_source_id == vs_id)
        .where(VideoSourceTag.tag_id == tag_id)
    )
    if entry:
        await session.delete(entry)
        await session.commit()
    return Response(status_code=204)


# ── 模板标签关联 ───────────────────────────────────────────────────────────────

@router.get("/video-ai-templates/{tpl_id}/tags", response_model=list[TagRead])
async def get_template_tags(
    tpl_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[TagRead]:
    """获取某模板的所有标签。"""
    stmt = (
        select(Tag)
        .join(VideoSourceTag, VideoSourceTag.tag_id == Tag.id)
        .where(VideoSourceTag.video_ai_template_id == tpl_id)
        .order_by(Tag.name.asc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [TagRead.model_validate(r) for r in rows]


@router.post("/video-ai-templates/{tpl_id}/tags", response_model=VideoSourceTagRead, status_code=201)
async def attach_tag_to_template(
    tpl_id: uuid.UUID,
    body: TagAttachBody,
    current_user: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> VideoSourceTagRead:
    """给AI模板打标签。"""
    tag = await session.get(Tag, body.tag_id)
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标签不存在")

    existing = await session.scalar(
        select(VideoSourceTag)
        .where(VideoSourceTag.video_ai_template_id == tpl_id)
        .where(VideoSourceTag.tag_id == body.tag_id)
    )
    if existing:
        return VideoSourceTagRead.model_validate(existing)

    entry = VideoSourceTag(
        owner_id=current_user.user_id,
        video_ai_template_id=tpl_id,
        tag_id=body.tag_id,
        created_at=_utcnow(),
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return VideoSourceTagRead.model_validate(entry)


@router.delete("/video-ai-templates/{tpl_id}/tags/{tag_id}", status_code=204)
async def detach_tag_from_template(
    tpl_id: uuid.UUID,
    tag_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    """移除模板的某个标签。"""
    entry = await session.scalar(
        select(VideoSourceTag)
        .where(VideoSourceTag.video_ai_template_id == tpl_id)
        .where(VideoSourceTag.tag_id == tag_id)
    )
    if entry:
        await session.delete(entry)
        await session.commit()
    return Response(status_code=204)
