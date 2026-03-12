from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenData, get_current_user
from app.db.session import get_db
from app.models.account_blogger_binding import AccountBloggerBinding
from app.models.account_tag import AccountTag
from app.models.tag import Tag
from app.models.tiktok_blogger import TiktokBlogger
from app.schemas.account import (
    AccountCreate, AccountListResponse, AccountPatch, AccountRead,
    BoundBloggerRead, BoundTagRead, ScheduledPublishConfig,
    AIGenerateBody, AIGenerateStatusResponse, BindTagBody,
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


async def _load_bound_tags(session: AsyncSession, account_id: uuid.UUID) -> list[BoundTagRead]:
    stmt = (
        select(Tag)
        .join(AccountTag, AccountTag.tag_id == Tag.id)
        .where(AccountTag.account_id == account_id)
        .order_by(AccountTag.created_at.asc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [BoundTagRead.model_validate(t) for t in rows]


def _account_read(account, bloggers: list[BoundBloggerRead], tags: list[BoundTagRead] | None = None) -> AccountRead:
    data = AccountRead.model_validate(account)
    data.tiktok_bloggers = bloggers
    data.bound_tags = tags or []
    return data


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
    page_size: int = Query(20, ge=1, le=100),
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> AccountListResponse:
    items, total = await list_accounts(session, page=page, page_size=page_size, owner_id=owner_id)
    # Batch-load bound bloggers and tags for all accounts.
    account_ids = [a.id for a in items]
    blogger_map: dict[uuid.UUID, list[BoundBloggerRead]] = {aid: [] for aid in account_ids}
    tag_map: dict[uuid.UUID, list[BoundTagRead]] = {aid: [] for aid in account_ids}
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

    rich_items = [_account_read(a, blogger_map[a.id], tag_map[a.id]) for a in items]
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
    return _account_read(account, bloggers, tags)


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
    return _account_read(account, bloggers, tags)


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
    return _account_read(account, bloggers, tags)


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

    # 优先从内存获取实时状态
    state = get_ai_account_state(str(account_id))
    if state:
        return AIGenerateStatusResponse(
            account_id=str(account_id),
            status=state.get("status", "idle"),
            error_message=state.get("error_message", ""),
            generated_name=state.get("generated_name", ""),
            generated_avatar_url=state.get("generated_avatar_url", ""),
            generated_photo_url=state.get("generated_photo_url", ""),
            combined_description=state.get("combined_description", ""),
        )

    # 回退到数据库中的状态
    return AIGenerateStatusResponse(
        account_id=str(account_id),
        status=account.ai_generation_status or "idle",
        error_message=account.ai_generation_error or "",
        generated_name="",
        generated_avatar_url=account.avatar_url or "",
        generated_photo_url=account.photo_url or "",
        combined_description="",
    )


@router.post("/{account_id}/ai-generate/resume", status_code=202)
async def resume_ai_generation(
    account_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """断点续跑：从上次失败/暂停的阶段继续。"""
    from app.services.ai_account_service import resume_ai_account_generation
    await get_account_or_404(session, account_id, owner_id)
    await resume_ai_account_generation(str(account_id))
    return {"status": "resuming"}


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


class BulkRestartAIBody(BaseModel):
    account_ids: list[str]


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
            aid = UUID(aid_str)
            acc = await session.get(Account, aid)
            if acc and acc.owner_id == owner_id:
                await restart_ai_account_generation(aid_str)
        except Exception as e:
            logger.error("Failed to restart account %s: %s", aid_str, e)

    return {"status": "restarted", "count": len(body.account_ids)}


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
