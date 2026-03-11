from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status

logger = logging.getLogger("app.video_ai_templates")
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.video_publication import VideoPublication
from app.models.video_task import VideoSubTask, VideoTask

from app.core.security import TokenData, get_current_user
from app.db.session import SessionLocal, get_db
from app.models.enums import VideoAIProcessStatus
from app.models.user import User
from app.models.tag import Tag, VideoSourceTag
from app.models.video_ai_template import VideoAITemplate
from app.models.video_source import VideoSource
from app.schemas.video_ai_template import (
    TagRead,
    VideoAITemplateCreate,
    VideoAITemplateListItem,
    VideoAITemplateListResponse,
    VideoAITemplatePatch,
    VideoAITemplateRead,
    VideoSourceSummary,
)
from app.services.video_ai_service import (
    enqueue_template,
    get_template_state,
    pause_template,
    restart_template,
    resume_template,
)

router = APIRouter(prefix="/video-ai-templates", tags=["video-ai-templates"])


def _get_owner_id(current_user: TokenData = Depends(get_current_user)) -> uuid.UUID | None:
    """查询过滤用：管理员返回 None（不过滤），普通用户返回自己的 user_id"""
    return None if current_user.is_admin else current_user.user_id


def _get_creator_id(current_user: TokenData = Depends(get_current_user)) -> uuid.UUID:
    """创建记录用：始终返回实际 user_id"""
    return current_user.user_id


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


async def _get_tpl_tags(session: AsyncSession, tpl_id: uuid.UUID) -> list[TagRead]:
    stmt = (
        select(Tag)
        .join(VideoSourceTag, VideoSourceTag.tag_id == Tag.id)
        .where(VideoSourceTag.video_ai_template_id == tpl_id)
        .order_by(Tag.name.asc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [TagRead.model_validate(r) for r in rows]


async def _to_read(session: AsyncSession, tpl: VideoAITemplate) -> VideoAITemplateRead:
    video_source = None
    if tpl.video_source_id:
        vs = await session.get(VideoSource, tpl.video_source_id)
        if vs:
            video_source = VideoSourceSummary.model_validate(vs)
    tags = await _get_tpl_tags(session, tpl.id)
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
        is_used=tpl.is_used,
        repeatable=tpl.repeatable,
        tiktok_blogger_id=tpl.tiktok_blogger_id,
        tags=tags,
        extra=tpl.extra,
        created_at=tpl.created_at,
        updated_at=tpl.updated_at,
    )


@router.post("", response_model=VideoAITemplateRead, status_code=201)
async def create_template(
    payload: VideoAITemplateCreate,
    creator_id: uuid.UUID = Depends(_get_creator_id),
    session: AsyncSession = Depends(get_db),
) -> VideoAITemplateRead:
    from datetime import datetime, timezone

    # 从原视频继承 repeatable 和 tiktok_blogger_id
    repeatable = False
    tiktok_blogger_id = None
    if payload.video_source_id:
        vs = await session.get(VideoSource, payload.video_source_id)
        if vs:
            repeatable = getattr(vs, "repeatable", False) or False
            tiktok_blogger_id = getattr(vs, "tiktok_blogger_id", None)

    tpl = VideoAITemplate(
        owner_id=creator_id,
        title=payload.title,
        description=payload.description,
        video_source_id=payload.video_source_id,
        process_status=VideoAIProcessStatus.pending,
        prompt_description=payload.prompt_description,
        extracted_shots=payload.extracted_shots,
        repeatable=repeatable,
        tiktok_blogger_id=tiktok_blogger_id,
        extra=payload.extra,
    )
    session.add(tpl)
    await session.flush()  # 获取 tpl.id

    # 关联标签：从 VideoSource 继承（更新现有记录，补充 video_ai_template_id）
    from sqlalchemy import select as sa_select
    from app.models.tag import VideoSourceTag

    if payload.video_source_id:
        tag_stmt = sa_select(VideoSourceTag).where(
            VideoSourceTag.video_source_id == payload.video_source_id
        )
        source_tags = (await session.execute(tag_stmt)).scalars().all()
        for st in source_tags:
            st.video_ai_template_id = tpl.id

    await session.commit()
    await session.refresh(tpl)
    return await _to_read(session, tpl)


@router.get("", response_model=VideoAITemplateListResponse)
async def list_templates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
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

    # 批量查询涉及的 owner_id 对应的用户名
    owner_ids = list({r.owner_id for r in rows if r.owner_id is not None})
    username_map: dict[uuid.UUID, str] = {}
    if owner_ids:
        users = (await session.execute(select(User).where(User.id.in_(owner_ids)))).scalars().all()
        for u in users:
            username_map[u.id] = u.display_name or u.username

    # 批量查询每个模板生成成功（非 pending/generating/abandon）的视频数
    tpl_ids = [r.id for r in rows]
    generated_count_map: dict[uuid.UUID, int] = {r.id: 0 for r in rows}
    if tpl_ids:
        _EXCLUDE_STATUSES = ("pending", "generating", "abandon")
        gen_stmt = (
            select(VideoTask.template_id, func.count(VideoSubTask.id).label("cnt"))
            .join(VideoSubTask, VideoSubTask.task_id == VideoTask.id)
            .where(VideoTask.template_id.in_(tpl_ids))
            .where(VideoSubTask.status.notin_(_EXCLUDE_STATUSES))
            .group_by(VideoTask.template_id)
        )
        for tpl_id, cnt in (await session.execute(gen_stmt)).all():
            if tpl_id in generated_count_map:
                generated_count_map[tpl_id] = cnt

    # 批量查询每个模板最近一次发布时间
    last_published_map: dict[uuid.UUID, datetime | None] = {r.id: None for r in rows}
    if tpl_ids:
        from datetime import datetime
        pub_stmt = (
            select(VideoTask.template_id, func.max(VideoPublication.created_at).label("last_pub"))
            .join(VideoSubTask, VideoSubTask.task_id == VideoTask.id)
            .join(VideoPublication, VideoPublication.sub_task_id == VideoSubTask.id)
            .where(VideoTask.template_id.in_(tpl_ids))
            .group_by(VideoTask.template_id)
        )
        for tpl_id, last_pub in (await session.execute(pub_stmt)).all():
            if tpl_id in last_published_map:
                last_published_map[tpl_id] = last_pub

    items_read = []
    for r in rows:
        vs = None
        if r.video_source_id:
            vs_obj = await session.get(VideoSource, r.video_source_id)
            if vs_obj:
                vs = VideoSourceSummary.model_validate(vs_obj)
        items_read.append(VideoAITemplateListItem(
            id=r.id,
            owner_id=r.owner_id,
            owner_username=username_map.get(r.owner_id) if r.owner_id else None,
            title=r.title,
            description=r.description,
            video_source_id=r.video_source_id,
            video_source=vs,
            process_status=r.process_status,
            process_error=r.process_error,
            prompt_description=r.prompt_description,
            extracted_shots=r.extracted_shots,
            is_used=r.is_used,
            repeatable=r.repeatable,
            tiktok_blogger_id=r.tiktok_blogger_id,
            generated_video_count=generated_count_map.get(r.id, 0),
            last_published_at=last_published_map.get(r.id),
            created_at=r.created_at,
            updated_at=r.updated_at,
        ))

    return VideoAITemplateListResponse(
        items=items_read,
        total=total,
        page=page,
        page_size=page_size,
    )


async def _do_batch_create_and_start(creator_id: uuid.UUID, owner_id: uuid.UUID | None) -> None:
    """后台异步：查询所有 download_status=done 且无模板的视频，批量创建模板并入队。"""
    try:
        async with SessionLocal() as session:
            # 1. 查所有 done 视频
            vs_stmt = select(VideoSource).where(VideoSource.download_status == "done")
            if owner_id is not None:
                vs_stmt = vs_stmt.where(VideoSource.owner_id == owner_id)
            all_vs = list((await session.execute(vs_stmt)).scalars().all())

            if not all_vs:
                logger.info("batch_create_and_start: no done videos found")
                return

            vs_ids = [vs.id for vs in all_vs]

            # 2. 查已有模板的 video_source_id
            existing_stmt = select(VideoAITemplate.video_source_id).where(
                VideoAITemplate.video_source_id.in_(vs_ids)
            )
            if owner_id is not None:
                existing_stmt = existing_stmt.where(VideoAITemplate.owner_id == owner_id)
            existing_ids = set((await session.execute(existing_stmt)).scalars().all())

            # 3. 批量创建
            vs_map = {vs.id: vs for vs in all_vs}
            new_tpls: list[VideoAITemplate] = []
            for vsid in vs_ids:
                if vsid in existing_ids:
                    continue
                vs = vs_map[vsid]
                tpl = VideoAITemplate(
                    owner_id=creator_id,
                    title=vs.video_title or vs.blogger_name or "新模板",
                    description="",
                    video_source_id=vsid,
                    process_status=VideoAIProcessStatus.pending,
                    repeatable=getattr(vs, "repeatable", False) or False,
                    tiktok_blogger_id=getattr(vs, "tiktok_blogger_id", None),
                )
                session.add(tpl)
                new_tpls.append(tpl)

            await session.commit()
            for tpl in new_tpls:
                await session.refresh(tpl)

            # 4. 复制 VideoSource 的标签到新的 Template（更新现有记录）
            from sqlalchemy import select as sa_select
            from collections import defaultdict
            tpl_vs_map = {tpl.id: tpl.video_source_id for tpl in new_tpls if tpl.video_source_id}
            if tpl_vs_map:
                # 查询这些 VideoSource 的所有标签关联
                tag_stmt = sa_select(VideoSourceTag).where(
                    VideoSourceTag.video_source_id.in_(set(tpl_vs_map.values()))
                )
                source_tags = (await session.execute(tag_stmt)).scalars().all()
                # 按 video_source_id 分组
                tags_by_vs: dict[uuid.UUID, list[VideoSourceTag]] = defaultdict(list)
                for st in source_tags:
                    tags_by_vs[st.video_source_id].append(st)
                # 为每个 Template 更新对应的标签记录（补充 video_ai_template_id）
                vs_to_tpl: dict[uuid.UUID, uuid.UUID] = {v: t for t, v in tpl_vs_map.items()}
                for st in source_tags:
                    if st.video_source_id in vs_to_tpl:
                        st.video_ai_template_id = vs_to_tpl[st.video_source_id]
                await session.commit()

            # 5. 批量入队（在 session 关闭后，enqueue 使用自己的 session）
        for tpl in new_tpls:
            await enqueue_template(str(tpl.id))

        logger.info(
            "batch_create_and_start done: created=%d skipped=%d",
            len(new_tpls), len(existing_ids),
        )
    except Exception as exc:
        logger.error("batch_create_and_start failed: %s", exc)


@router.post("/batch-create-and-start", status_code=status.HTTP_202_ACCEPTED)
async def batch_create_and_start(
    creator_id: uuid.UUID = Depends(_get_creator_id),
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
) -> dict[str, str]:
    """触发后台批量创建模板，立即返回 202。"""
    asyncio.create_task(_do_batch_create_and_start(creator_id, owner_id))
    return {"status": "accepted"}


@router.get("/all-available", response_model=list[VideoAITemplateListItem])
async def list_all_available_templates(
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> list[VideoAITemplateListItem]:
    """获取所有可用的视频 AI 模板（无分页），用于批量生成选择。"""
    stmt = (
        select(VideoAITemplate)
        .where(VideoAITemplate.process_status == VideoAIProcessStatus.success)
        .order_by(VideoAITemplate.created_at.desc())
    )
    if owner_id is not None:
        stmt = stmt.where(VideoAITemplate.owner_id == owner_id)

    rows = (await session.execute(stmt)).scalars().all()

    owner_ids = list({r.owner_id for r in rows if r.owner_id is not None})
    username_map: dict[uuid.UUID, str] = {}
    if owner_ids:
        users = (await session.execute(select(User).where(User.id.in_(owner_ids)))).scalars().all()
        for u in users:
            username_map[u.id] = u.display_name or u.username

    vs_ids = list({r.video_source_id for r in rows if r.video_source_id is not None})
    vs_map: dict[uuid.UUID, VideoSource] = {}
    if vs_ids:
        video_sources = (await session.execute(select(VideoSource).where(VideoSource.id.in_(vs_ids)))).scalars().all()
        for v in video_sources:
            vs_map[v.id] = v

    items_read = []
    for r in rows:
        vs = None
        if r.video_source_id and r.video_source_id in vs_map:
            vs = VideoSourceSummary.model_validate(vs_map[r.video_source_id])
        items_read.append(VideoAITemplateListItem(
            id=r.id,
            owner_id=r.owner_id,
            owner_username=username_map.get(r.owner_id) if r.owner_id else None,
            title=r.title,
            description=r.description,
            video_source_id=r.video_source_id,
            video_source=vs,
            process_status=r.process_status,
            process_error=r.process_error,
            prompt_description=r.prompt_description,
            extracted_shots=r.extracted_shots,
            is_used=r.is_used,
            repeatable=r.repeatable,
            tiktok_blogger_id=r.tiktok_blogger_id,
            created_at=r.created_at,
            updated_at=r.updated_at,
        ))

    return items_read


@router.get("/by-blogger/{blogger_id}", response_model=list[VideoAITemplateListItem])
async def list_templates_by_blogger(
    blogger_id: uuid.UUID,
    tag_ids: str | None = Query(None, description="逗号分隔的 tag_id，用于按标签过滤"),
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> list[VideoAITemplateListItem]:
    """获取指定TikTok博主关联的所有成功模板，用于生成页按博主选模板。支持按 tag_ids 过滤。"""
    from sqlalchemy import exists

    stmt = (
        select(VideoAITemplate)
        .where(VideoAITemplate.tiktok_blogger_id == blogger_id)
        .where(VideoAITemplate.process_status == VideoAIProcessStatus.success)
        .order_by(VideoAITemplate.created_at.desc())
    )
    if owner_id is not None:
        stmt = stmt.where(VideoAITemplate.owner_id == owner_id)

    # 按标签过滤：模板必须包含所有指定标签
    if tag_ids:
        filter_tag_ids = [uuid.UUID(t.strip()) for t in tag_ids.split(",") if t.strip()]
        for tid in filter_tag_ids:
            stmt = stmt.where(
                exists().where(
                    VideoSourceTag.video_ai_template_id == VideoAITemplate.id,
                ).where(VideoSourceTag.tag_id == tid)
            )

    rows = (await session.execute(stmt)).scalars().all()

    vs_ids = list({r.video_source_id for r in rows if r.video_source_id is not None})
    vs_map: dict[uuid.UUID, VideoSource] = {}
    if vs_ids:
        video_sources = (await session.execute(select(VideoSource).where(VideoSource.id.in_(vs_ids)))).scalars().all()
        for v in video_sources:
            vs_map[v.id] = v

    # 批量查询模板标签
    tpl_ids = [r.id for r in rows]
    tags_map: dict[uuid.UUID, list[TagRead]] = {r.id: [] for r in rows}
    if tpl_ids:
        tag_stmt = (
            select(VideoSourceTag.video_ai_template_id, Tag)
            .join(Tag, Tag.id == VideoSourceTag.tag_id)
            .where(VideoSourceTag.video_ai_template_id.in_(tpl_ids))
            .order_by(Tag.name.asc())
        )
        for tpl_id, tag in (await session.execute(tag_stmt)).all():
            if tpl_id in tags_map:
                tags_map[tpl_id].append(TagRead.model_validate(tag))

    items_read = []
    for r in rows:
        vs = None
        if r.video_source_id and r.video_source_id in vs_map:
            vs = VideoSourceSummary.model_validate(vs_map[r.video_source_id])
        items_read.append(VideoAITemplateListItem(
            id=r.id,
            owner_id=r.owner_id,
            title=r.title,
            description=r.description,
            video_source_id=r.video_source_id,
            video_source=vs,
            process_status=r.process_status,
            process_error=r.process_error,
            prompt_description=r.prompt_description,
            extracted_shots=r.extracted_shots,
            is_used=r.is_used,
            repeatable=r.repeatable,
            tiktok_blogger_id=r.tiktok_blogger_id,
            tags=tags_map.get(r.id, []),
            created_at=r.created_at,
            updated_at=r.updated_at,
        ))

    return items_read


@router.get("/stats", response_model=dict[str, int])
async def get_template_stats(
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Return count per process_status."""
    from sqlalchemy import func, text

    stmt = select(
        VideoAITemplate.process_status,
        func.count(VideoAITemplate.id).label("cnt"),
    ).group_by(VideoAITemplate.process_status)
    if owner_id is not None:
        stmt = stmt.where(VideoAITemplate.owner_id == owner_id)
    rows = (await session.execute(stmt)).all()
    return {str(row[0].value if hasattr(row[0], "value") else row[0]): row[1] for row in rows}


@router.get("/by-video-source-ids", response_model=dict[str, str])
async def get_templates_by_video_source_ids(
    ids: str = Query(..., description="Comma-separated video_source_id list"),
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Return {video_source_id: template_id} for all given video_source_ids that have a template."""
    from sqlalchemy import func

    try:
        vs_ids = [uuid.UUID(s.strip()) for s in ids.split(",") if s.strip()]
    except ValueError:
        return {}
    if not vs_ids:
        return {}

    stmt = select(VideoAITemplate.video_source_id, VideoAITemplate.id).where(
        VideoAITemplate.video_source_id.in_(vs_ids)
    )
    if owner_id is not None:
        stmt = stmt.where(VideoAITemplate.owner_id == owner_id)

    rows = (await session.execute(stmt)).all()
    # If multiple templates per video_source, return the first (latest by default order)
    result: dict[str, str] = {}
    for vs_id, tpl_id in rows:
        key = str(vs_id)
        if key not in result:
            result[key] = str(tpl_id)
    return result


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


@router.post("/{tpl_id}/restart", response_model=VideoAITemplateRead)
async def restart_template_endpoint(
    tpl_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> VideoAITemplateRead:
    tpl = await _get_tpl_or_404(session, tpl_id, owner_id)
    await restart_template(str(tpl.id))
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
    extra = tpl.extra or {}
    if state is None:
        # Return DB state
        return {
            "template_id": str(tpl.id),
            "status": tpl.process_status.value,
            "error_message": tpl.process_error or "",
            "prompt_description": tpl.prompt_description or "",
            "extracted_shots": tpl.extracted_shots or [],
            "extra": extra,
        }
    return {**state, "extra": extra}


@router.post("/{tpl_id}/mark-used", response_model=VideoAITemplateRead)
async def mark_template_used(
    tpl_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> VideoAITemplateRead:
    """标记模板为已使用。"""
    tpl = await _get_tpl_or_404(session, tpl_id, owner_id)
    tpl.is_used = True
    await session.commit()
    await session.refresh(tpl)
    return await _to_read(session, tpl)


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


