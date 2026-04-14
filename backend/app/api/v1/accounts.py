from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

import random

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenData, get_current_user
from app.db.session import get_db
from app.models.account import Account
from app.models.account_blogger_binding import AccountBloggerBinding
from app.models.account_tag import AccountTag
from app.models.flag import AccountFlag, Flag
from app.models.tag import Tag
from app.models.tag import VideoSourceTag
from app.models.tiktok_blogger import TiktokBlogger
from app.models.video_task import VideoSubTask, VideoTask
from app.schemas.account import (
    AccountCreate, AccountListResponse, AccountPatch, AccountRead,
    BoundBloggerRead, BoundFlagRead, BoundTagRead, ScheduledPublishConfig,
    AIGenerateBody, AIGenerateStatusResponse, BindTagBody, BulkGenerateAIAccountsResponse,
    BulkResumeAIAccountsResponse, ResumeAIGenerationBody, SelectPhotoCandidateBody,
    BulkGenerateNameHandleBody, BulkGenerateNameHandleResponse,
)
from app.schemas.tiktok_blogger import TiktokBloggerRead
from app.services.account_service import (
    create_account,
    delete_account,
    get_account_or_404,
    list_accounts,
    patch_account,
)

router = APIRouter(prefix="/accounts", tags=["accounts"])
logger = logging.getLogger("app.accounts")


class BindBloggerBody(BaseModel):
    tiktok_blogger_id: uuid.UUID


async def _load_bound_bloggers(session: AsyncSession, account_id: uuid.UUID) -> list[BoundBloggerRead]:
    stmt = (
        select(TiktokBlogger)
        .join(AccountBloggerBinding, AccountBloggerBinding.tiktok_blogger_id == TiktokBlogger.id)
        .where(AccountBloggerBinding.account_id == account_id)
        .order_by(AccountBloggerBinding.created_at.asc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [BoundBloggerRead.model_validate(b) for b in rows]


async def _load_bound_flags(session: AsyncSession, account_id: uuid.UUID) -> list[BoundFlagRead]:
    stmt = (
        select(Flag)
        .join(AccountFlag, AccountFlag.flag_id == Flag.id)
        .where(AccountFlag.account_id == account_id)
        .order_by(AccountFlag.created_at.asc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [BoundFlagRead.model_validate(f) for f in rows]


async def _load_bound_tags(session: AsyncSession, account_id: uuid.UUID) -> list[BoundTagRead]:
    stmt = (
        select(Tag)
        .join(AccountTag, AccountTag.tag_id == Tag.id)
        .where(AccountTag.account_id == account_id)
        .order_by(AccountTag.created_at.asc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [BoundTagRead.model_validate(t) for t in rows]


def _account_read(
    account,
    bloggers: list[BoundBloggerRead],
    tags: list[BoundTagRead] | None = None,
    flags: list[BoundFlagRead] | None = None,
    pending_publish_count: int = 0,
) -> AccountRead:
    data = AccountRead.model_validate(account)
    data.tiktok_bloggers = bloggers
    data.bound_tags = tags or []
    data.bound_flags = flags or []
    data.pending_publish_count = pending_publish_count
    return data


def _ai_generation_response(account_id: uuid.UUID, state: dict, account) -> AIGenerateStatusResponse:
    return AIGenerateStatusResponse(
        account_id=str(account_id),
        status=state.get("status", account.ai_generation_status or "idle"),
        error_message=state.get("error_message", account.ai_generation_error or ""),
        all_video_count=state.get("all_video_count", 0),
        analysis_sample_size=state.get("analysis_sample_size", 10),
        analysis_video_ids=state.get("analysis_video_ids", []) or [],
        analysis_items=state.get("analysis_items", []) or [],
        generated_name=state.get("generated_name", ""),
        generated_avatar_url=state.get("generated_avatar_url", account.avatar_url or ""),
        generated_photo_url=state.get("generated_photo_url", account.photo_url or ""),
        generated_painting_url=state.get("generated_painting_url", account.painting_url or ""),
        photo_candidate_count=state.get("photo_candidate_count", 0),
        photo_candidates=state.get("photo_candidates", []) or [],
        selected_photo_candidate_id=state.get("selected_photo_candidate_id"),
        combined_description=state.get("combined_description", ""),
    )


def _get_owner_id(current_user: TokenData = Depends(get_current_user)) -> uuid.UUID | None:
    """For queries: admin sees all (None = no filter), regular user sees own only."""
    return None if current_user.is_admin else current_user.user_id


def _get_creator_id(current_user: TokenData = Depends(get_current_user)) -> uuid.UUID:
    """For writes: always bind to the actual user, even if admin."""
    return current_user.user_id


@router.post("", response_model=AccountRead, status_code=201)
async def create_account_endpoint(
    payload: AccountCreate,
    creator_id: uuid.UUID = Depends(_get_creator_id),
    session: AsyncSession = Depends(get_db),
) -> AccountRead:
    account = await create_account(session, payload, creator_id)
    return _account_read(account, [], [])


@router.get("", response_model=AccountListResponse)
async def list_accounts_endpoint(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=9999),
    flag_id: uuid.UUID | None = Query(None),
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> AccountListResponse:
    items, total = await list_accounts(session, page=page, page_size=page_size, owner_id=owner_id, flag_id=flag_id)
    # Batch-load bound bloggers, tags, flags for all accounts.
    account_ids = [a.id for a in items]
    blogger_map: dict[uuid.UUID, list[BoundBloggerRead]] = {aid: [] for aid in account_ids}
    tag_map: dict[uuid.UUID, list[BoundTagRead]] = {aid: [] for aid in account_ids}
    flag_map: dict[uuid.UUID, list[BoundFlagRead]] = {aid: [] for aid in account_ids}
    pending_publish_map: dict[uuid.UUID, int] = {aid: 0 for aid in account_ids}
    if account_ids:
        blogger_stmt = (
            select(AccountBloggerBinding.account_id, TiktokBlogger)
            .join(TiktokBlogger, AccountBloggerBinding.tiktok_blogger_id == TiktokBlogger.id)
            .where(AccountBloggerBinding.account_id.in_(account_ids))
            .order_by(AccountBloggerBinding.created_at.asc())
        )
        for aid, blogger in (await session.execute(blogger_stmt)).all():
            blogger_map[aid].append(BoundBloggerRead.model_validate(blogger))

        tag_stmt = (
            select(AccountTag.account_id, Tag)
            .join(Tag, AccountTag.tag_id == Tag.id)
            .where(AccountTag.account_id.in_(account_ids))
            .order_by(AccountTag.created_at.asc())
        )
        for aid, tag in (await session.execute(tag_stmt)).all():
            tag_map[aid].append(BoundTagRead.model_validate(tag))

        flag_stmt = (
            select(AccountFlag.account_id, Flag)
            .join(Flag, AccountFlag.flag_id == Flag.id)
            .where(AccountFlag.account_id.in_(account_ids))
            .order_by(AccountFlag.created_at.asc())
        )
        for aid, flag in (await session.execute(flag_stmt)).all():
            flag_map[aid].append(BoundFlagRead.model_validate(flag))

        pending_publish_stmt = (
            select(VideoTask.account_id, func.count(VideoSubTask.id))
            .join(VideoSubTask, VideoSubTask.task_id == VideoTask.id)
            .where(
                VideoTask.account_id.in_(account_ids),
                VideoSubTask.status == "queued",
            )
            .group_by(VideoTask.account_id)
        )
        for aid, count in (await session.execute(pending_publish_stmt)).all():
            if aid is not None:
                pending_publish_map[aid] = int(count or 0)

    rich_items = [
        _account_read(
            a,
            blogger_map[a.id],
            tag_map[a.id],
            flag_map[a.id],
            pending_publish_map[a.id],
        )
        for a in items
    ]
    return AccountListResponse(
        items=rich_items,  # type: ignore[arg-type]
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{account_id}", response_model=AccountRead)
async def get_account_endpoint(
    account_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> AccountRead:
    account = await get_account_or_404(session, account_id, owner_id)
    bloggers = await _load_bound_bloggers(session, account_id)
    tags = await _load_bound_tags(session, account_id)
    flags = await _load_bound_flags(session, account_id)
    return _account_read(account, bloggers, tags, flags)


@router.patch("/{account_id}", response_model=AccountRead)
async def patch_account_endpoint(
    account_id: uuid.UUID,
    payload: AccountPatch,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> AccountRead:
    account = await get_account_or_404(session, account_id, owner_id)
    account = await patch_account(session, account, payload)
    bloggers = await _load_bound_bloggers(session, account_id)
    tags = await _load_bound_tags(session, account_id)
    flags = await _load_bound_flags(session, account_id)
    return _account_read(account, bloggers, tags, flags)


@router.delete("/{account_id}")
async def delete_account_endpoint(
    account_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> Response:
    await delete_account(session, account_id, owner_id)
    return Response(status_code=204)


# ── 定时发布配置 ────────────────────────────────────────────────────────────────

@router.put("/{account_id}/scheduled-publish", response_model=AccountRead)
async def update_scheduled_publish(
    account_id: uuid.UUID,
    payload: ScheduledPublishConfig,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> AccountRead:
    """更新 AI 博主账号的定时发布配置"""
    account = await get_account_or_404(session, account_id, owner_id)
    account.publish_enabled = payload.publish_enabled
    account.publish_cron = payload.publish_cron
    account.publish_window_minutes = payload.publish_window_minutes
    account.publish_count = payload.publish_count
    await session.commit()
    await session.refresh(account)
    bloggers = await _load_bound_bloggers(session, account_id)
    tags = await _load_bound_tags(session, account_id)
    flags = await _load_bound_flags(session, account_id)
    return _account_read(account, bloggers, tags, flags)


# ── 账号-博主绑定 ─────────────────────────────────────────────────────────────

@router.get("/{account_id}/bloggers", response_model=list[TiktokBloggerRead])
async def list_account_bloggers(
    account_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> list[TiktokBloggerRead]:
    """获取账号已绑定的TikTok博主列表。"""
    await get_account_or_404(session, account_id, owner_id)
    stmt = (
        select(TiktokBlogger)
        .join(AccountBloggerBinding, AccountBloggerBinding.tiktok_blogger_id == TiktokBlogger.id)
        .where(AccountBloggerBinding.account_id == account_id)
        .order_by(AccountBloggerBinding.created_at.asc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [
        TiktokBloggerRead(
            **{k: getattr(b, k) for k in TiktokBloggerRead.model_fields if k != "video_count" and hasattr(b, k)},
            video_count=0,
        )
        for b in rows
    ]


@router.post("/{account_id}/bloggers", status_code=201)
async def bind_blogger_to_account(
    account_id: uuid.UUID,
    body: BindBloggerBody,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """绑定TikTok博主到账号。"""
    await get_account_or_404(session, account_id, owner_id)

    blogger = await session.get(TiktokBlogger, body.tiktok_blogger_id)
    if not blogger:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="博主不存在")

    existing = await session.scalar(
        select(AccountBloggerBinding)
        .where(AccountBloggerBinding.account_id == account_id)
        .where(AccountBloggerBinding.tiktok_blogger_id == body.tiktok_blogger_id)
    )
    if existing:
        return {"status": "already_bound"}

    binding = AccountBloggerBinding(
        account_id=account_id,
        tiktok_blogger_id=body.tiktok_blogger_id,
        created_at=datetime.now(timezone.utc),
    )
    session.add(binding)
    await session.commit()
    return {"status": "bound"}


@router.delete("/{account_id}/bloggers/{blogger_id}")
async def unbind_blogger_from_account(
    account_id: uuid.UUID,
    blogger_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """解绑TikTok博主与账号的关联。"""
    await get_account_or_404(session, account_id, owner_id)
    binding = await session.scalar(
        select(AccountBloggerBinding)
        .where(AccountBloggerBinding.account_id == account_id)
        .where(AccountBloggerBinding.tiktok_blogger_id == blogger_id)
    )
    if binding:
        await session.delete(binding)
        await session.commit()
    return Response(status_code=204)


# ── AI 生成 ──────────────────────────────────────────────────────────────────

@router.post("/{account_id}/ai-generate", status_code=202)
async def trigger_ai_generation(
    account_id: uuid.UUID,
    body: AIGenerateBody,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """触发 AI 生成博主名称、头像和照片。"""
    from app.services.ai_account_service import enqueue_ai_account_generation

    await get_account_or_404(session, account_id, owner_id)

    # 先将标签绑定到账号
    tag_ids_str = [str(tid) for tid in body.tag_ids]
    for tag_id in body.tag_ids:
        tag = await session.get(Tag, tag_id)
        if not tag:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"标签 {tag_id} 不存在")
        existing = await session.scalar(
            select(AccountTag)
            .where(AccountTag.account_id == account_id)
            .where(AccountTag.tag_id == tag_id)
        )
        if not existing:
            session.add(AccountTag(account_id=account_id, tag_id=tag_id))
    await session.commit()

    await enqueue_ai_account_generation(str(account_id), tag_ids_str)
    return {"status": "queued"}


@router.get("/{account_id}/ai-generate/status", response_model=AIGenerateStatusResponse)
async def get_ai_generation_status(
    account_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> AIGenerateStatusResponse:
    """查询 AI 生成状态。"""
    from app.services.ai_account_service import get_ai_account_state

    account = await get_account_or_404(session, account_id, owner_id)

    state = get_ai_account_state(str(account_id))
    if not state:
        state = account.ai_generation_state or {}
    return _ai_generation_response(account_id, state, account)


@router.post("/{account_id}/ai-generate/resume", status_code=202)
async def resume_ai_generation(
    account_id: uuid.UUID,
    body: ResumeAIGenerationBody | None = None,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """断点续跑：从上次失败/暂停的阶段继续。"""
    from app.services.ai_account_service import resume_ai_account_generation
    await get_account_or_404(session, account_id, owner_id)
    status_value = await resume_ai_account_generation(
        str(account_id),
        from_stage=(body.from_stage if body else "current"),
    )
    return {"status": status_value}


@router.post("/{account_id}/ai-generate/restart", status_code=202)
async def restart_ai_generation(
    account_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """从头重试：清空所有已完成阶段，重新执行完整流程。"""
    from app.services.ai_account_service import restart_ai_account_generation
    await get_account_or_404(session, account_id, owner_id)
    await restart_ai_account_generation(str(account_id))
    return {"status": "restarting"}


@router.post("/{account_id}/ai-generate/select-photo", response_model=AIGenerateStatusResponse)
async def select_ai_generation_photo(
    account_id: uuid.UUID,
    body: SelectPhotoCandidateBody,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> AIGenerateStatusResponse:
    from app.services.ai_account_service import select_ai_account_photo_candidate

    account = await get_account_or_404(session, account_id, owner_id)
    try:
        state = await select_ai_account_photo_candidate(str(account_id), body.candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    refreshed_account = await get_account_or_404(session, account_id, owner_id)
    return _ai_generation_response(account_id, state, refreshed_account)


class BulkRestartAIBody(BaseModel):
    account_ids: list[str]


@router.post("/bulk-resume-ai-generation", response_model=BulkResumeAIAccountsResponse, status_code=202)
async def bulk_resume_ai_generation(
    body: ResumeAIGenerationBody,
    current_user: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> BulkResumeAIAccountsResponse:
    from app.services.ai_account_service import resume_ai_account_generation

    owner_id = current_user.user_id

    stmt = select(Account.id).where(Account.owner_id == owner_id)

    # 指定账号列表时限定范围
    if body.account_ids:
        stmt = stmt.where(Account.id.in_(body.account_ids))

    # stage 筛选逻辑始终生效
    if body.from_stage == "current":
        stmt = (
            stmt
            .where(Account.ai_generation_status != "completed")
            .where(Account.ai_generation_status != "awaiting_photo_selection")
        )
    else:
        stmt = stmt.where(
            or_(
                Account.ai_generation_status != "idle",
                Account.ai_generation_state.is_not(None),
                Account.photo_url.is_not(None),
                Account.avatar_url.is_not(None),
            )
        )

    stmt = stmt.order_by(Account.created_at.desc())
    account_ids = [str(aid) for aid in (await session.execute(stmt)).scalars().all()]
    if not account_ids:
        return BulkResumeAIAccountsResponse(status="no_accounts", from_stage=body.from_stage)

    resumed_count = 0
    skipped_count = 0
    for aid_str in account_ids:
        try:
            result = await resume_ai_account_generation(aid_str, from_stage=body.from_stage)
            if result in {"resuming", "already_running"}:
                resumed_count += 1
            else:
                skipped_count += 1
        except Exception as exc:
            skipped_count += 1
            logger.error("Failed to bulk resume account %s from stage %s: %s", aid_str, body.from_stage, exc)

    return BulkResumeAIAccountsResponse(
        status="resumed",
        resumed_count=resumed_count,
        skipped_count=skipped_count,
        from_stage=body.from_stage,
    )


@router.post("/bulk-generate-ai-bloggers", response_model=BulkGenerateAIAccountsResponse, status_code=202)
async def bulk_generate_ai_bloggers(
    creator_id: uuid.UUID = Depends(_get_creator_id),
    session: AsyncSession = Depends(get_db),
) -> BulkGenerateAIAccountsResponse:
    """为还没有绑定 AI 博主账号的标签批量创建账号并入队生成。"""
    from app.services.ai_account_service import enqueue_ai_account_generation

    tags_stmt = (
        select(Tag)
        .where(Tag.owner_id == creator_id)
        .where(
            exists(
                select(VideoSourceTag.id)
                .where(VideoSourceTag.tag_id == Tag.id)
                .where(VideoSourceTag.owner_id == creator_id)
                .where(VideoSourceTag.video_source_id.is_not(None))
            )
        )
        .where(
            ~exists(
                select(AccountTag.id)
                .join(Account, Account.id == AccountTag.account_id)
                .where(AccountTag.tag_id == Tag.id)
                .where(Account.owner_id == creator_id)
            )
        )
        .order_by(Tag.created_at.asc())
    )
    tags = (await session.execute(tags_stmt)).scalars().all()
    if not tags:
        return BulkGenerateAIAccountsResponse(status="no_tags")

    created_accounts: list[Account] = []
    created_tag_ids: list[str] = []
    for tag in tags:
        account = Account(
            owner_id=creator_id,
            account_name=f"AI博主生成中 · {tag.name}",
            ai_generation_status="idle",
        )
        session.add(account)
        await session.flush()
        session.add(AccountTag(account_id=account.id, tag_id=tag.id))

        # 通过 tag → video_source_tags → video_sources 找到 tiktok_blogger_id 并绑定
        from app.models.video_source import VideoSource as _VS
        blogger_id_row = (
            await session.execute(
                select(_VS.tiktok_blogger_id)
                .join(VideoSourceTag, VideoSourceTag.video_source_id == _VS.id)
                .where(VideoSourceTag.tag_id == tag.id)
                .where(VideoSourceTag.video_source_id.is_not(None))
                .where(_VS.tiktok_blogger_id.is_not(None))
                .limit(1)
            )
        ).first()
        if blogger_id_row:
            session.add(AccountBloggerBinding(
                account_id=account.id,
                tiktok_blogger_id=blogger_id_row[0],
            ))

        created_accounts.append(account)
        created_tag_ids.append(str(tag.id))

    await session.commit()

    for account, tag_id in zip(created_accounts, created_tag_ids, strict=False):
        await enqueue_ai_account_generation(str(account.id), [tag_id])

    return BulkGenerateAIAccountsResponse(
        status="queued",
        created_count=len(created_accounts),
        skipped_count=0,
        queued_count=len(created_accounts),
        created_account_ids=[str(account.id) for account in created_accounts],
        skipped_tag_ids=[],
    )


@router.post("/bulk-restart-ai-generation", status_code=202)
async def bulk_restart_ai_generation(
    body: BulkRestartAIBody,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """批量重启失败的 AI 生成任务。"""
    from app.services.ai_account_service import restart_ai_account_generation

    if not body.account_ids:
        return {"status": "no_accounts"}

    # 验证权限并获取账号
    await get_account_or_404(session, uuid.UUID(body.account_ids[0]), owner_id)

    # 批量重启
    for aid_str in body.account_ids:
        try:
            aid = uuid.UUID(aid_str)
            acc = await session.get(Account, aid)
            if acc and acc.owner_id == owner_id:
                await restart_ai_account_generation(aid_str)
        except Exception as e:
            logger.error("Failed to restart account %s: %s", aid_str, e)

    return {"status": "restarted", "count": len(body.account_ids)}


@router.post("/bulk-generate-name-handle", response_model=BulkGenerateNameHandleResponse, status_code=202)
async def bulk_generate_name_handle(
    body: BulkGenerateNameHandleBody,
    current_user: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> BulkGenerateNameHandleResponse:
    """批量为账号 AI 生成名称/Handle/签名。"""
    from app.services.name_handle_service import enqueue_name_handle_generation

    owner_id = current_user.user_id
    stmt = select(Account.id).where(Account.owner_id == owner_id)
    if body.account_ids:
        stmt = stmt.where(Account.id.in_(body.account_ids))

    account_ids = [str(aid) for aid in (await session.execute(stmt)).scalars().all()]
    if not account_ids:
        return BulkGenerateNameHandleResponse(status="no_accounts", queued_count=0)

    queued_count = await enqueue_name_handle_generation(account_ids)
    return BulkGenerateNameHandleResponse(status="queued", queued_count=queued_count)


# ── 账号-标签绑定 ──────────────────────────────────────────────────────────────

@router.get("/{account_id}/tags", response_model=list[BoundTagRead])
async def list_account_tags(
    account_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> list[BoundTagRead]:
    """获取账号已绑定的标签列表。"""
    await get_account_or_404(session, account_id, owner_id)
    return await _load_bound_tags(session, account_id)


@router.post("/{account_id}/tags", status_code=201)
async def bind_tag_to_account(
    account_id: uuid.UUID,
    body: BindTagBody,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """绑定标签到账号。"""
    await get_account_or_404(session, account_id, owner_id)
    tag = await session.get(Tag, body.tag_id)
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标签不存在")
    existing = await session.scalar(
        select(AccountTag)
        .where(AccountTag.account_id == account_id)
        .where(AccountTag.tag_id == body.tag_id)
    )
    if existing:
        return {"status": "already_bound"}
    session.add(AccountTag(account_id=account_id, tag_id=body.tag_id))
    await session.commit()
    return {"status": "bound"}


@router.delete("/{account_id}/tags/{tag_id}")
async def unbind_tag_from_account(
    account_id: uuid.UUID,
    tag_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """解绑标签与账号的关联。"""
    await get_account_or_404(session, account_id, owner_id)
    binding = await session.scalar(
        select(AccountTag)
        .where(AccountTag.account_id == account_id)
        .where(AccountTag.tag_id == tag_id)
    )
    if binding:
        await session.delete(binding)
        await session.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# 补充模板
# ---------------------------------------------------------------------------

class SupplementTemplatesBody(BaseModel):
    account_ids: list[uuid.UUID]
    template_type: str = "shared"  # "shared" | "exclusive"
    max_new_videos: int = 10


# ---------------------------------------------------------------------------
# 一键生成视频任务
# ---------------------------------------------------------------------------

class BulkGenerateVideoTasksBody(BaseModel):
    account_ids: list[uuid.UUID]
    mode: str = "unused"         # "unused" | "used"
    limit: int = 0               # 每账号最多使用模板数，0 = 不限制
    subtask_count: int = 3       # 每个任务创建的子任务数量


@router.post("/bulk-generate-video-tasks", status_code=200)
async def bulk_generate_video_tasks(
    body: BulkGenerateVideoTasksBody,
    current_user: TokenData = Depends(get_current_user),
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """
    为指定账号批量创建视频生成任务。
    mode=unused: 选取未使用(is_used=False)的模板，按创建时间顺序取前 limit 个。
    mode=used:   选取已使用(is_used=True)的模板，随机打乱后取前 limit 个。
    """
    from app.models.video_ai_template import VideoAITemplate
    from app.models.video_source import VideoSource
    from app.models.enums import VideoAIProcessStatus
    from app.services.video_task_service import VideoTaskService

    if not body.account_ids:
        return {"message": "无账号，跳过", "created": 0, "failed": 0, "skipped": 0}

    use_used = body.mode == "used"
    svc = VideoTaskService(db=session)

    total_created = 0
    total_failed = 0
    total_skipped = 0

    for account_id in body.account_ids:
        try:
            # 路径1：通过绑定博主获取模板
            blogger_stmt = (
                select(TiktokBlogger)
                .join(AccountBloggerBinding, AccountBloggerBinding.tiktok_blogger_id == TiktokBlogger.id)
                .where(AccountBloggerBinding.account_id == account_id)
            )
            bloggers = (await session.execute(blogger_stmt)).scalars().all()

            candidate_tpls: list[VideoAITemplate] = []

            if bloggers:
                for blogger in bloggers:
                    tpl_stmt = (
                        select(VideoAITemplate)
                        .where(VideoAITemplate.tiktok_blogger_id == blogger.id)
                        .where(VideoAITemplate.process_status == VideoAIProcessStatus.success)
                        .where(VideoAITemplate.is_used == use_used)
                        .order_by(VideoAITemplate.created_at.asc())
                    )
                    if owner_id is not None:
                        tpl_stmt = tpl_stmt.where(VideoAITemplate.owner_id == owner_id)
                    rows = (await session.execute(tpl_stmt)).scalars().all()
                    candidate_tpls.extend(rows)
            else:
                # 路径2：无绑定博主时，通过账号绑定的标签获取模板
                tag_stmt = select(AccountTag.tag_id).where(AccountTag.account_id == account_id)
                tag_ids = list((await session.execute(tag_stmt)).scalars().all())
                if tag_ids:
                    for tid in tag_ids:
                        tpl_stmt = (
                            select(VideoAITemplate)
                            .where(VideoAITemplate.process_status == VideoAIProcessStatus.success)
                            .where(VideoAITemplate.is_used == use_used)
                            .where(
                                exists().where(
                                    VideoSourceTag.video_ai_template_id == VideoAITemplate.id,
                                    VideoSourceTag.tag_id == tid,
                                )
                            )
                            .order_by(VideoAITemplate.created_at.asc())
                        )
                        if owner_id is not None:
                            tpl_stmt = tpl_stmt.where(VideoAITemplate.owner_id == owner_id)
                        rows = (await session.execute(tpl_stmt)).scalars().all()
                        candidate_tpls.extend(rows)

            # 去重
            seen: set[uuid.UUID] = set()
            unique_tpls: list[VideoAITemplate] = []
            for t in candidate_tpls:
                if t.id not in seen:
                    seen.add(t.id)
                    unique_tpls.append(t)

            if not unique_tpls:
                total_skipped += 1
                continue

            # used 模式随机打乱
            pool = random.sample(unique_tpls, len(unique_tpls)) if use_used else unique_tpls
            items_to_use = pool[:body.limit] if body.limit > 0 else pool

            # 预加载 video_source duration
            vs_ids = list({t.video_source_id for t in items_to_use if t.video_source_id})
            vs_map: dict[uuid.UUID, VideoSource] = {}
            if vs_ids:
                vs_rows = (await session.execute(select(VideoSource).where(VideoSource.id.in_(vs_ids)))).scalars().all()
                for vs in vs_rows:
                    vs_map[vs.id] = vs

            for tpl in items_to_use:
                try:
                    dur_s = 0
                    if tpl.video_source_id and tpl.video_source_id in vs_map:
                        dur_s = vs_map[tpl.video_source_id].duration or 0
                    dur_s = min(int(dur_s), 15)
                    duration = f"{dur_s}s" if dur_s else "0s"

                    shots = [
                        {k: v for k, v in s.items() if k != "image_base64"}
                        for s in (tpl.extracted_shots or [])
                    ]
                    await svc.create_task(
                        account_id=account_id,
                        template_id=tpl.id,
                        final_prompt=tpl.prompt_description or "",
                        duration=duration,
                        shots=shots,
                        user_id=current_user.user_id,
                        subtask_count=body.subtask_count,
                    )
                    total_created += 1
                except Exception:
                    total_failed += 1
        except Exception:
            total_skipped += 1

    return {
        "message": f"已创建 {total_created} 个生成任务，{total_failed} 个失败，{total_skipped} 个账号跳过",
        "created": total_created,
        "failed": total_failed,
        "skipped": total_skipped,
    }


@router.post("/supplement-templates", status_code=200)
async def supplement_templates(
    body: SupplementTemplatesBody,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
):
    """
    为指定账号批量补充模板（后台异步执行，立即返回）。
    """
    from app.services.candidate_service import supplement_templates_for_accounts
    import asyncio as _asyncio

    if not body.account_ids:
        return {"message": "无账号，跳过", "count": 0}

    template_type = body.template_type if body.template_type in ("shared", "exclusive") else "shared"

    _asyncio.create_task(
        supplement_templates_for_accounts(
            account_ids=body.account_ids,
            owner_id=owner_id,
            template_type=template_type,
            max_new_videos=body.max_new_videos,
        )
    )

    return {
        "message": f"已为 {len(body.account_ids)} 个账号启动补充模板任务（{template_type}）",
        "count": len(body.account_ids),
    }
