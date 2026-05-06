from __future__ import annotations

import hmac
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.account import Account
from app.models.account_channel_reservation import AccountChannelReservation
from app.services.channel_status_poller import refresh_reservation_channel_status
from app.schemas.account import (
    ExternalBindOpenAPIChannelBody,
    ExternalBindOpenAPIChannelResponse,
    ExternalAIAccountCandidateItem,
    ExternalChannelReservationRead,
    ExternalConfirmChannelReservationBody,
    ExternalConfirmChannelReservationResponse,
    ExternalReserveAIAccountsBody,
    ExternalReserveAIAccountsResponse,
    ExternalReleaseChannelReservationBody,
)

router = APIRouter(prefix="/open-api/accounts", tags=["open-api-account-channels"])
logger = logging.getLogger("app.account_channel_reservations")


def _mask_api_key(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 6:
        return "***"
    return f"{value[:4]}***{value[-2:]}"


def _resolve_owner_id(body_owner_id: uuid.UUID | None) -> uuid.UUID:
    if body_owner_id is not None:
        return body_owner_id
    default = settings.account_channel_owner_id
    if not default:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="owner_id 未传且服务端未配置 ACCOUNT_CHANNEL_OWNER_ID",
        )
    try:
        return uuid.UUID(default)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务端 ACCOUNT_CHANNEL_OWNER_ID 格式无效",
        )


def _verify_api_key(body_api_key: str = "", header_api_key: str | None = None) -> None:
    expected = settings.account_channel_api_key
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ACCOUNT_CHANNEL_API_KEY 未配置",
        )
    supplied = header_api_key or body_api_key or ""
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid api_key")


def _channel_binding_payload(body: ExternalBindOpenAPIChannelBody) -> dict:
    return {
        "platform": body.platform,
        "channel_source": body.channel_source or "openapi",
        "channel_id": body.channel_id,
        "channel_name": body.channel_name,
        "username": body.username,
    }


def _apply_channel_binding(
    reservation: AccountChannelReservation,
    binding: dict,
    *,
    now: datetime,
) -> None:
    source = str(binding.get("channel_source") or binding.get("source") or reservation.source or "openapi")
    reservation.status = "bound"
    reservation.source = source
    reservation.channel_source = source
    reservation.channel_id = str(binding.get("channel_id") or "") or None
    reservation.channel_name = str(binding.get("channel_name") or "") or None
    reservation.username = str(binding.get("username") or "") or None
    reservation.avatar_url = str(binding.get("avatar_url") or "") or None
    reservation.channel_info = None
    reservation.confirmed_at = reservation.confirmed_at or now
    reservation.bound_at = now


@router.post("/channel-reservations", response_model=ExternalReserveAIAccountsResponse, status_code=201)
async def reserve_ai_accounts_for_channel_openapi(
    body: ExternalReserveAIAccountsBody,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_db),
) -> ExternalReserveAIAccountsResponse:
    """外部团队按 owner、性别、平台查询可用 AI 博主，并立即 confirm 占用，避免并发重复领取。"""
    logger.info(
        "reserve_ai_accounts request: owner_id=%s gender=%s platform=%s count=%s source=%s "
        "api_key_header=%s api_key_body=%s",
        body.owner_id,
        body.gender,
        body.platform,
        body.count,
        body.source,
        _mask_api_key(x_api_key),
        _mask_api_key(body.api_key),
    )
    _verify_api_key(body.api_key, x_api_key)
    owner_id = _resolve_owner_id(body.owner_id)

    platform = body.platform.lower()
    # FOR UPDATE SKIP LOCKED: 并发请求各自锁定不重叠的行，保证 count 准确
    stmt = (
        select(Account)
        .where(Account.owner_id == owner_id)
        .where(Account.gender == body.gender)
        .where(Account.ai_generation_status == "completed")
        .where(
            ~exists()
            .where(AccountChannelReservation.account_id == Account.id)
            .where(AccountChannelReservation.platform == platform)
        )
        .order_by(Account.created_at.asc())
        .limit(body.count)
        .with_for_update(skip_locked=True)
    )

    now = datetime.now(timezone.utc)
    items: list[ExternalAIAccountCandidateItem] = []
    confirmed_count = 0

    accounts = (await session.execute(stmt)).scalars().all()
    for account in accounts:
        reservation = AccountChannelReservation(
            account_id=account.id,
            platform=platform,
            status="confirmed",
            source=body.source,
            channel_source=body.source,
            reserved_at=now,
            confirmed_at=now,
        )
        session.add(reservation)
        confirmed_count += 1
        items.append(
            ExternalAIAccountCandidateItem(
                account_id=account.id,
                platform=body.platform,
                account_name=account.account_name,
                account_handle=account.account_handle,
                account_signature=account.account_signature,
                hashtags=account.hashtags,
                avatar_url=account.avatar_url,
                confirmed=True,
            )
        )

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="部分账号已被其他请求占用，请稍后重试",
        )
    response = ExternalReserveAIAccountsResponse(
        items=items,
        requested_count=body.count,
        returned_count=len(items),
        confirmed_count=confirmed_count,
    )
    logger.info(
        "reserve_ai_accounts response summary: owner_id=%s platform=%s requested=%s returned=%s confirmed=%s account_ids=%s",
        owner_id,
        platform,
        body.count,
        len(items),
        confirmed_count,
        [str(it.account_id) for it in items],
    )
    logger.info(
        "reserve_ai_accounts response body: %s",
        response.model_dump(mode="json"),
    )
    return response


@router.post("/channel-reservations/confirm", response_model=ExternalConfirmChannelReservationResponse)
async def confirm_channel_reservation_openapi(
    body: ExternalConfirmChannelReservationBody,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> ExternalConfirmChannelReservationResponse:
    """占用已由 reserve 接口完成，此接口直接返回成功（兼容旧调用方）。"""
    _verify_api_key(body.api_key, x_api_key)
    owner_id = _resolve_owner_id(body.owner_id)
    return ExternalConfirmChannelReservationResponse(
        status="confirmed",
        owner_id=owner_id,
        account_id=body.account_id,
        platform=body.platform,
    )


@router.post("/{account_id}/channel-bindings", response_model=ExternalBindOpenAPIChannelResponse)
async def bind_openapi_channel_openapi(
    account_id: uuid.UUID,
    body: ExternalBindOpenAPIChannelBody,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_db),
) -> ExternalBindOpenAPIChannelResponse:
    """外部团队绑定频道信息到 AI 博主。"""
    _verify_api_key(body.api_key, x_api_key)
    owner_id = _resolve_owner_id(body.owner_id)

    account = await session.scalar(
        select(Account)
        .where(Account.id == account_id)
        .where(Account.owner_id == owner_id)
    )
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")

    platform = body.platform.lower()
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
            source=body.channel_source or "openapi",
            channel_source=body.channel_source or "openapi",
            reserved_at=now,
            confirmed_at=now,
        )
        session.add(reservation)
    elif reservation.status == "bound":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"该账号 {platform} 平台已绑定，不可修改；请先调用 release 释放",
        )

    _apply_channel_binding(reservation, _channel_binding_payload(body), now=now)
    await refresh_reservation_channel_status(reservation)
    await session.commit()
    rows = (
        await session.execute(
            select(AccountChannelReservation)
            .where(AccountChannelReservation.account_id == account_id)
            .order_by(AccountChannelReservation.created_at.asc())
        )
    ).scalars().all()
    return ExternalBindOpenAPIChannelResponse(
        account_id=account.id,
        account_name=account.account_name,
        account_handle=account.account_handle,
        account_signature=account.account_signature,
        gender=account.gender,
        account_type=account.account_type,
        channel_reservations=[ExternalChannelReservationRead.model_validate(row) for row in rows],
    )


@router.post("/channel-reservations/release", status_code=200)
async def release_channel_reservation_openapi(
    body: ExternalReleaseChannelReservationBody,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """解绑并删除 AI 博主的平台频道占用记录，解绑后该博主可重新被领取绑定。"""
    _verify_api_key(body.api_key, x_api_key)
    owner_id = _resolve_owner_id(body.owner_id)

    account = await session.scalar(
        select(Account)
        .where(Account.id == body.account_id)
        .where(Account.owner_id == owner_id)
    )
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")

    platform = body.platform.lower()
    reservation = await session.scalar(
        select(AccountChannelReservation)
        .where(AccountChannelReservation.account_id == body.account_id)
        .where(AccountChannelReservation.platform == platform)
    )
    if not reservation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到该平台的绑定记录")

    await session.delete(reservation)
    await session.commit()
    return {"account_id": str(body.account_id), "platform": body.platform, "released": True}
