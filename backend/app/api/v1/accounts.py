from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

import random

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenData, get_current_user
from app.db.session import get_db
from app.models.account import Account
from app.models.account_blogger_binding import AccountBloggerBinding
from app.models.account_channel_reservation import AccountChannelReservation
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
    AccountChannelReservationRead, BindOpenAPIChannelBody, ConfirmChannelReservationsBody,
    ConfirmChannelReservationsResponse, ReserveAIAccountsBody, ReserveAIAccountsResponse,
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


async def _load_channel_reservations(
    session: AsyncSession,
    account_id: uuid.UUID,
) -> list[AccountChannelReservationRead]:
    stmt = (
        select(AccountChannelReservation)
        .where(AccountChannelReservation.account_id == account_id)
        .order_by(AccountChannelReservation.created_at.asc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [AccountChannelReservationRead.model_validate(r) for r in rows]


def _channel_binding_payload(body: BindOpenAPIChannelBody) -> dict:
    data = body.model_dump(exclude_none=True)
    extra = data.pop("extra", None) or {}
    data.update(extra)
    data["platform"] = body.platform
    data["source"] = body.source or "openapi"
    return data


def _reservation_to_binding(reservation: AccountChannelReservation | AccountChannelReservationRead) -> dict:
    base = {
        "platform": reservation.platform,
        "channel_source": reservation.channel_source or reservation.source or "openapi",
        "channel_id": reservation.channel_id or "",
        "channel_name": reservation.channel_name or "",
        "username": reservation.username or "",
    }
    avatar_url = getattr(reservation, "avatar_url", None)
    if avatar_url:
        base["avatar_url"] = avatar_url
    return base


def _apply_channel_binding(
    reservation: AccountChannelReservation,
    binding: dict,
    *,
    now: datetime,
) -> None:
    platform = str(binding.get("platform") or reservation.platform or "").lower()
    source = str(binding.get("channel_source") or binding.get("source") or reservation.source or "openapi")
    reservation.platform = platform
    reservation.status = "bound"
    reservation.source = source
    reservation.channel_source = source
    reservation.channel_id = str(binding.get("channel_id") or "") or None
    reservation.channel_name = str(binding.get("channel_name") or "") or None
    reservation.username = str(binding.get("username") or "") or None
    reservation.avatar_url = str(binding.get("avatar_url") or "") or None
    reservation.channel_info = {**binding, "platform": platform, "channel_source": source}
    reservation.confirmed_at = reservation.confirmed_at or now
    reservation.bound_at = now


async def _sync_channel_reservations_from_bindings(
    session: AsyncSession,
    account: Account,
    bindings: list[dict] | None,
) -> None:
    """把接口传入的频道绑定写入结构化频道表。"""
    supported_platforms = {"youtube", "tiktok", "instagram"}
    desired: dict[str, dict] = {}
    for binding in bindings or []:
        if not isinstance(binding, dict):
            continue
        platform = str(binding.get("platform") or "").lower()
        if platform in supported_platforms:
            desired[platform] = {**binding, "platform": platform}

    rows = (await session.execute(
        select(AccountChannelReservation)
        .where(AccountChannelReservation.account_id == account.id)
        .where(AccountChannelReservation.platform.in_(supported_platforms))
    )).scalars().all()
    existing_by_platform = {r.platform: r for r in rows}
    now = datetime.now(timezone.utc)

    for platform, binding in desired.items():
        reservation = existing_by_platform.get(platform)
        if reservation is None:
            reservation = AccountChannelReservation(
                account_id=account.id,
                platform=platform,
                reserved_at=now,
                confirmed_at=now,
            )
            session.add(reservation)
        elif reservation.status == "bound":
            # bound 记录受保护，跳过修改
            continue
        _apply_channel_binding(reservation, binding, now=now)

    for platform, reservation in existing_by_platform.items():
        if platform not in desired and reservation.status == "bound" and reservation.confirmed_at is None:
            await session.delete(reservation)

    await session.commit()


def _account_read(
    account,
    bloggers: list[BoundBloggerRead],
    tags: list[BoundTagRead] | None = None,
    flags: list[BoundFlagRead] | None = None,
    pending_publish_count: int = 0,
    channel_reservations: list[AccountChannelReservationRead] | None = None,
) -> AccountRead:
    data = AccountRead.model_validate(account)
    data.tiktok_bloggers = bloggers
    data.bound_tags = tags or []
    data.bound_flags = flags or []
    data.pending_publish_count = pending_publish_count
    data.channel_reservations = channel_reservations or []
    data.social_bindings = None
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
    if payload.social_bindings is not None:
        await _sync_channel_reservations_from_bindings(session, account, payload.social_bindings)
    reservations = await _load_channel_reservations(session, account.id)
    return _account_read(account, [], [], channel_reservations=reservations)


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
    reservation_map: dict[uuid.UUID, list[AccountChannelReservationRead]] = {aid: [] for aid in account_ids}
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

        reservation_stmt = (
            select(AccountChannelReservation)
            .where(AccountChannelReservation.account_id.in_(account_ids))
            .order_by(AccountChannelReservation.created_at.asc())
        )
        for reservation in (await session.execute(reservation_stmt)).scalars().all():
            reservation_map[reservation.account_id].append(AccountChannelReservationRead.model_validate(reservation))

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
            reservation_map[a.id],
        )
        for a in items
    ]
    return AccountListResponse(
        items=rich_items,  # type: ignore[arg-type]
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/channel-reservations", response_model=ReserveAIAccountsResponse, status_code=201)
async def reserve_ai_accounts_for_channel(
    body: ReserveAIAccountsBody,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> ReserveAIAccountsResponse:
    """按性别和平台领取 AI 博主，并立即占用该平台名额。"""
    platform = body.platform.lower()
    reserved_accounts: list[Account] = []
    reservations: list[AccountChannelReservation] = []
    seen_account_ids: set[uuid.UUID] = set()
    batch_size = max(body.count * 5, 50)
    while len(reserved_accounts) < body.count:
        stmt = (
            select(Account)
            .where(Account.gender == body.gender)
            .where(
                ~exists()
                .where(AccountChannelReservation.account_id == Account.id)
                .where(AccountChannelReservation.platform == platform)
            )
            .order_by(Account.created_at.asc())
            .limit(batch_size)
        )
        if owner_id is not None:
            stmt = stmt.where(Account.owner_id == owner_id)
        if seen_account_ids:
            stmt = stmt.where(Account.id.not_in(list(seen_account_ids)))
        candidates = (await session.execute(stmt)).scalars().all()
        if not candidates:
            break
        for account in candidates:
            seen_account_ids.add(account.id)
            if len(reserved_accounts) >= body.count:
                break
            reservation = AccountChannelReservation(
                account_id=account.id,
                platform=platform,
                status="reserved",
                source=body.source or "openapi",
                channel_source=body.source or "openapi",
                reserved_at=datetime.now(timezone.utc),
            )
            session.add(reservation)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                continue
            await session.refresh(reservation)
            reserved_accounts.append(account)
            reservations.append(reservation)

    items: list[AccountRead] = []
    for account, reservation in zip(reserved_accounts, reservations, strict=False):
        bloggers = await _load_bound_bloggers(session, account.id)
        tags = await _load_bound_tags(session, account.id)
        flags = await _load_bound_flags(session, account.id)
        items.append(
            _account_read(
                account,
                bloggers,
                tags,
                flags,
                channel_reservations=[AccountChannelReservationRead.model_validate(reservation)],
            )
        )

    return ReserveAIAccountsResponse(
        items=items,
        requested_count=body.count,
        reserved_count=len(items),
        reservation_ids=[r.id for r in reservations],
    )


@router.post("/channel-reservations/confirm", response_model=ConfirmChannelReservationsResponse)
async def confirm_channel_reservations(
    body: ConfirmChannelReservationsBody,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> ConfirmChannelReservationsResponse:
    """确认外部调用方确实占用了这些 AI 博主的平台频道。"""
    stmt = select(AccountChannelReservation).join(Account, Account.id == AccountChannelReservation.account_id)
    if body.reservation_ids:
        stmt = stmt.where(AccountChannelReservation.id.in_(body.reservation_ids))
    else:
        if not body.account_ids or not body.platform:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="reservation_ids 或 account_ids + platform 必须提供一组",
            )
        stmt = stmt.where(AccountChannelReservation.account_id.in_(body.account_ids))
        stmt = stmt.where(AccountChannelReservation.platform == body.platform)
    if owner_id is not None:
        stmt = stmt.where(Account.owner_id == owner_id)

    rows = (await session.execute(stmt)).scalars().all()
    now = datetime.now(timezone.utc)
    confirmed_ids: list[uuid.UUID] = []
    for reservation in rows:
        if reservation.status != "bound":
            reservation.status = "confirmed"
            reservation.confirmed_at = reservation.confirmed_at or now
        confirmed_ids.append(reservation.id)
    await session.commit()
    return ConfirmChannelReservationsResponse(
        status="confirmed",
        confirmed_count=len(confirmed_ids),
        reservation_ids=confirmed_ids,
    )


@router.post("/{account_id}/channel-bindings", response_model=AccountRead)
async def bind_openapi_channel(
    account_id: uuid.UUID,
    body: BindOpenAPIChannelBody,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> AccountRead:
    """保存 OpenAPI 回传的平台频道信息。"""
    account = await get_account_or_404(session, account_id, owner_id)
    platform = body.platform.lower()
    binding = _channel_binding_payload(body)

    reservation = await session.scalar(
        select(AccountChannelReservation)
        .where(AccountChannelReservation.account_id == account_id)
        .where(AccountChannelReservation.platform == platform)
    )
    now = datetime.now(timezone.utc)
    if reservation is None:
        reservation = AccountChannelReservation(
            account_id=account_id,
            platform=platform,
            source=body.source or "openapi",
            channel_source=body.source or "openapi",
            reserved_at=now,
            confirmed_at=now,
        )
        session.add(reservation)
    elif reservation.status == "bound":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"该账号 {platform} 平台已绑定，不可修改；请先调用 release 释放",
        )
    _apply_channel_binding(reservation, binding, now=now)

    await session.commit()
    await session.refresh(account)
    bloggers = await _load_bound_bloggers(session, account_id)
    tags = await _load_bound_tags(session, account_id)
    flags = await _load_bound_flags(session, account_id)
    reservations = await _load_channel_reservations(session, account_id)
    return _account_read(account, bloggers, tags, flags, channel_reservations=reservations)


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
    reservations = await _load_channel_reservations(session, account_id)
    return _account_read(account, bloggers, tags, flags, channel_reservations=reservations)


@router.patch("/{account_id}", response_model=AccountRead)
async def patch_account_endpoint(
    account_id: uuid.UUID,
    payload: AccountPatch,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> AccountRead:
    account = await get_account_or_404(session, account_id, owner_id)
    account = await patch_account(session, account, payload)
    if payload.social_bindings is not None:
        await _sync_channel_reservations_from_bindings(session, account, payload.social_bindings)
    bloggers = await _load_bound_bloggers(session, account_id)
    tags = await _load_bound_tags(session, account_id)
    flags = await _load_bound_flags(session, account_id)
    reservations = await _load_channel_reservations(session, account_id)
    return _account_read(account, bloggers, tags, flags, channel_reservations=reservations)


@router.delete("/{account_id}/channel-reservations/{reservation_id}")
async def delete_channel_reservation(
    account_id: uuid.UUID,
    reservation_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """删除一条频道绑定（channel_reservation）。仅允许删除 bound 状态的记录。"""
    await get_account_or_404(session, account_id, owner_id)
    reservation = await session.scalar(
        select(AccountChannelReservation)
        .where(AccountChannelReservation.id == reservation_id)
        .where(AccountChannelReservation.account_id == account_id)
    )
    if reservation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="频道绑定不存在")
    if reservation.status != "bound":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="只能删除已绑定（bound）状态的频道",
        )
    await session.delete(reservation)
    await session.commit()
    return Response(status_code=204)


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
    reservations = await _load_channel_reservations(session, account_id)
    return _account_read(account, bloggers, tags, flags, channel_reservations=reservations)


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
    只根据账号绑定的标签查找模板，不再根据已绑定的 TikTok 博主筛选模板。
    mode=unused: 选取未使用(is_used=False)的模板，按创建时间倒序取前 limit 个。
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
            candidate_tpls: list[VideoAITemplate] = []
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
                        .order_by(VideoAITemplate.created_at.desc())
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


# ---------------------------------------------------------------------------
# 标签搜索（Hashtag Search）
# ---------------------------------------------------------------------------

class BulkSearchHashtagsBody(BaseModel):
    account_ids: list[uuid.UUID] | None = None  # None = 当前用户全部账号
    mode: str = "replace"                        # "replace" | "merge"


@router.post("/bulk-search-hashtags", status_code=202)
async def bulk_search_hashtags(
    body: BulkSearchHashtagsBody,
    current_user: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """
    批量标签搜索并绑定（后台异步执行）：
    1. 找到所选账号绑定的 TikTok 博主
    2. 用 Apify 抓取每个博主最热门视频（top_n 由配置决定，默认 100）
    3. 提取 hashtag 去重
    4. AI 过滤（需在 AI博主配置中填写提示词）
    5. 将结果写入各账号的 hashtags 字段（mode=replace 覆盖 / mode=merge 追加）
    """
    import asyncio as _asyncio
    from app.services.hashtag_search_service import search_and_bind_hashtags_for_accounts

    owner_id = current_user.user_id

    # 确定账号范围
    stmt = select(Account.id).where(Account.owner_id == owner_id)
    if body.account_ids:
        stmt = stmt.where(Account.id.in_(body.account_ids))
    account_ids = [str(aid) for aid in (await session.execute(stmt)).scalars().all()]

    if not account_ids:
        raise HTTPException(status_code=400, detail="没有找到符合条件的账号")

    _asyncio.create_task(
        search_and_bind_hashtags_for_accounts(
            account_ids=account_ids,
            owner_id=str(owner_id),
            mode=body.mode,
        )
    )
    return {"status": "queued", "account_count": len(account_ids)}


class BulkBindHashtagsBody(BaseModel):
    account_ids: list[uuid.UUID] | None = None  # None = 当前用户全部账号
    hashtags: list[str]                          # 要绑定的 hashtag 列表（不含 #）
    mode: str = "replace"                        # "replace" | "merge"


@router.post("/bulk-bind-hashtags", status_code=200)
async def bulk_bind_hashtags(
    body: BulkBindHashtagsBody,
    current_user: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """
    将 hashtag 列表批量绑定到指定账号。
    mode=replace：直接覆盖账号的 hashtags 字段。
    mode=merge：与现有 hashtags 合并去重。
    """
    owner_id = current_user.user_id

    stmt = select(Account).where(Account.owner_id == owner_id)
    if body.account_ids:
        stmt = stmt.where(Account.id.in_(body.account_ids))
    accounts = (await session.execute(stmt)).scalars().all()

    if not accounts:
        return {"updated_count": 0, "message": "没有找到符合条件的账号"}

    clean_tags = [t.strip().lstrip("#") for t in body.hashtags if t.strip()]

    for acc in accounts:
        if body.mode == "merge" and acc.hashtags:
            existing = list(acc.hashtags)
            existing_lower = {t.lower() for t in existing}
            merged = existing + [t for t in clean_tags if t.lower() not in existing_lower]
            acc.hashtags = merged
        else:
            acc.hashtags = clean_tags

    await session.commit()
    return {"updated_count": len(accounts), "message": f"已为 {len(accounts)} 个账号绑定 {len(clean_tags)} 个标签"}
