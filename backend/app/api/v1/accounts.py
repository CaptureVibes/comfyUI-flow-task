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
from app.models.tiktok_blogger import TiktokBlogger
from app.schemas.account import AccountCreate, AccountListResponse, AccountPatch, AccountRead, BoundBloggerRead, ScheduledPublishConfig
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


def _account_read(account, bloggers: list[BoundBloggerRead]) -> AccountRead:
    data = AccountRead.model_validate(account)
    data.tiktok_bloggers = bloggers
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
    return _account_read(account, [])


@router.get("", response_model=AccountListResponse)
async def list_accounts_endpoint(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> AccountListResponse:
    items, total = await list_accounts(session, page=page, page_size=page_size, owner_id=owner_id)
    # Batch-load bound bloggers for all accounts
    account_ids = [a.id for a in items]
    blogger_map: dict[uuid.UUID, list[BoundBloggerRead]] = {aid: [] for aid in account_ids}
    if account_ids:
        stmt = (
            select(AccountBloggerBinding.account_id, TiktokBlogger)
            .join(TiktokBlogger, AccountBloggerBinding.tiktok_blogger_id == TiktokBlogger.id)
            .where(AccountBloggerBinding.account_id.in_(account_ids))
            .order_by(AccountBloggerBinding.created_at.asc())
        )
        for aid, blogger in (await session.execute(stmt)).all():
            blogger_map[aid].append(BoundBloggerRead.model_validate(blogger))
    rich_items = [_account_read(a, blogger_map[a.id]) for a in items]
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
    return _account_read(account, bloggers)


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
    return _account_read(account, bloggers)


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
    return _account_read(account, bloggers)


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
