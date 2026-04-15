from __future__ import annotations

import hmac
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
from app.schemas.account import (
    ExternalBindOpenAPIChannelBody,
    ExternalBindOpenAPIChannelResponse,
    ExternalAIAccountCandidateItem,
    ExternalChannelReservationRead,
    ExternalConfirmChannelReservationBody,
    ExternalConfirmChannelReservationResponse,
    ExternalReserveAIAccountsBody,
    ExternalReserveAIAccountsResponse,
)

router = APIRouter(prefix="/open-api/accounts", tags=["open-api-account-channels"])


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
    """外部团队按 owner、性别、平台查询可用 AI 博主；不写库、不占用。"""
    _verify_api_key(body.api_key, x_api_key)
    owner_id = _resolve_owner_id(body.owner_id)

    platform = body.platform.lower()
    stmt = (
        select(Account)
        .where(Account.owner_id == owner_id)
        .where(Account.gender == body.gender)
        .where(
            ~exists()
            .where(AccountChannelReservation.account_id == Account.id)
            .where(AccountChannelReservation.platform == platform)
        )
        .order_by(Account.created_at.asc())
        .limit(body.count)
    )
    accounts = (await session.execute(stmt)).scalars().all()

    items = [
        ExternalAIAccountCandidateItem(
            account_id=account.id,
            platform=body.platform,
            account_name=account.account_name,
            account_handle=account.account_handle,
            account_signature=account.account_signature,
            hashtags=account.hashtags,
            avatar_url=account.avatar_url,
        )
        for account in accounts
    ]
    return ExternalReserveAIAccountsResponse(
        items=items,
        requested_count=body.count,
        returned_count=len(items),
    )


@router.post("/channel-reservations/confirm", response_model=ExternalConfirmChannelReservationResponse)
async def confirm_channel_reservation_openapi(
    body: ExternalConfirmChannelReservationBody,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_db),
) -> ExternalConfirmChannelReservationResponse:
    """外部团队逐条确认一个 account_id + platform，占用从这里才真正写库。"""
    _verify_api_key(body.api_key, x_api_key)
    owner_id = _resolve_owner_id(body.owner_id)

    platform = body.platform.lower()
    account = await session.scalar(
        select(Account)
        .where(Account.id == body.account_id)
        .where(Account.owner_id == owner_id)
    )
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")

    existing = await session.scalar(
        select(AccountChannelReservation)
        .where(AccountChannelReservation.account_id == body.account_id)
        .where(AccountChannelReservation.platform == platform)
    )
    now = datetime.now(timezone.utc)
    if existing:
        if existing.status != "bound":
            existing.status = "confirmed"
            existing.confirmed_at = existing.confirmed_at or now
        await session.commit()
        return ExternalConfirmChannelReservationResponse(
            status=existing.status,
            owner_id=owner_id,
            account_id=body.account_id,
            platform=body.platform,
        )

    reservation = AccountChannelReservation(
        account_id=body.account_id,
        platform=platform,
        status="confirmed",
        source="openapi",
        channel_source="openapi",
        reserved_at=now,
        confirmed_at=now,
    )
    session.add(reservation)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该账号平台已被占用") from None
    return ExternalConfirmChannelReservationResponse(
        status=reservation.status,
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

    _apply_channel_binding(reservation, _channel_binding_payload(body), now=now)
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
