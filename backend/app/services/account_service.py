from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import Float, delete, func, nullslast, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.account_channel_reservation import AccountChannelReservation
from app.models.flag import AccountFlag
from app.schemas.account import AccountCreate, AccountPatch, BulkUpdateAccountAttributesBody

# Sortable columns backed by performance_snapshot JSON keys
_SNAPSHOT_SORT_FIELDS = {
    "avg_views": "performance_snapshot->>'avg_views'",
    "avg_like_rate": "performance_snapshot->>'avg_like_rate'",
    "latest_video_published_at": "performance_snapshot->>'latest_video_published_at'",
    "followers_count": "performance_snapshot->>'followers_count'",
    "total_views": "performance_snapshot->>'total_views'",
}

# Sortable columns on the Account table itself
_TABLE_SORT_FIELDS = {
    "created_at": Account.created_at,
}


async def create_account(
    session: AsyncSession,
    payload: AccountCreate,
    owner_id: UUID | None = None,
) -> Account:
    account = Account(
        owner_id=owner_id,
        account_name=payload.account_name,
        account_type=payload.account_type,
        product_code_mode=payload.product_code_mode,
        face_mode=payload.face_mode,
        gender=payload.gender,
        style_description=payload.style_description,
        model_appearance=payload.model_appearance,
        avatar_url=payload.avatar_url,
        photo_url=payload.photo_url,
        hashtags=payload.hashtags if payload.hashtags else None,
    )
    session.add(account)
    await session.commit()
    await session.refresh(account)
    return account


async def list_accounts(
    session: AsyncSession,
    *,
    page: int,
    page_size: int,
    owner_id: UUID | None = None,
    flag_id: UUID | None = None,
    search: str | None = None,
    sort_by: str | None = None,
    sort_order: str | None = None,
    gender: str | None = None,
    account_type: str | None = None,
    face_mode: str | None = None,
    product_code_mode: str | None = None,
    platform_binding_status: str | None = None,
    classification_type: str | None = None,
) -> tuple[list[Account], int]:
    # ── Determine sort order ──────────────────────────────────────────────────
    order_desc = (sort_order or "desc").lower() == "desc"

    if sort_by and sort_by in _SNAPSHOT_SORT_FIELDS:
        json_expr = _SNAPSHOT_SORT_FIELDS[sort_by]
        # Extract the raw JSON text value via a literal column expression
        raw_col = text(json_expr)
        if sort_by in ("avg_views", "avg_like_rate", "followers_count", "total_views"):
            # Cast to float so numeric ordering works correctly
            typed_col = func.cast(func.nullif(raw_col, ""), Float)
        else:
            # Date strings in ISO format sort correctly as text
            typed_col = func.nullif(raw_col, "")
        order_clause = nullslast(typed_col.desc() if order_desc else typed_col.asc())
    elif sort_by and sort_by in _TABLE_SORT_FIELDS:
        col = _TABLE_SORT_FIELDS[sort_by]
        order_clause = col.desc() if order_desc else col.asc()
    else:
        order_clause = Account.created_at.desc()

    stmt = select(Account).order_by(order_clause).offset((page - 1) * page_size).limit(page_size)
    total_stmt = select(func.count(Account.id))

    # ── Filters ───────────────────────────────────────────────────────────────
    if owner_id is not None:
        stmt = stmt.where(Account.owner_id == owner_id)
        total_stmt = total_stmt.where(Account.owner_id == owner_id)
    if flag_id is not None:
        flag_subq = select(AccountFlag.account_id).where(AccountFlag.flag_id == flag_id)
        stmt = stmt.where(Account.id.in_(flag_subq))
        total_stmt = total_stmt.where(Account.id.in_(flag_subq))
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(Account.account_name.ilike(pattern))
        total_stmt = total_stmt.where(Account.account_name.ilike(pattern))
    if gender:
        stmt = stmt.where(Account.gender == gender)
        total_stmt = total_stmt.where(Account.gender == gender)
    if account_type:
        stmt = stmt.where(Account.account_type == account_type)
        total_stmt = total_stmt.where(Account.account_type == account_type)
    if face_mode:
        stmt = stmt.where(Account.face_mode == face_mode)
        total_stmt = total_stmt.where(Account.face_mode == face_mode)
    if product_code_mode:
        stmt = stmt.where(Account.product_code_mode == product_code_mode)
        total_stmt = total_stmt.where(Account.product_code_mode == product_code_mode)
    if platform_binding_status:
        # "bound" = has at least one reservation with status='bound'
        # "confirmed" = has at least one reservation with status='confirmed'
        # "unbound" = has no reservations at all
        if platform_binding_status == "unbound":
            bound_subq = select(AccountChannelReservation.account_id)
            stmt = stmt.where(~Account.id.in_(bound_subq))
            total_stmt = total_stmt.where(~Account.id.in_(bound_subq))
        elif platform_binding_status in ("bound", "confirmed"):
            status_subq = (
                select(AccountChannelReservation.account_id)
                .where(AccountChannelReservation.status == platform_binding_status)
            )
            stmt = stmt.where(Account.id.in_(status_subq))
            total_stmt = total_stmt.where(Account.id.in_(status_subq))
    if classification_type:
        if classification_type == "unclassified":
            stmt = stmt.where(Account.classification_type.is_(None))
            total_stmt = total_stmt.where(Account.classification_type.is_(None))
        else:
            stmt = stmt.where(Account.classification_type == classification_type)
            total_stmt = total_stmt.where(Account.classification_type == classification_type)

    rows = (await session.execute(stmt)).scalars().all()
    total = int(await session.scalar(total_stmt) or 0)
    return list(rows), total


async def get_account_or_404(
    session: AsyncSession,
    account_id: UUID,
    owner_id: UUID | None = None,
) -> Account:
    account = await session.scalar(select(Account).where(Account.id == account_id))
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
    if owner_id is not None and account.owner_id != owner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
    return account


async def patch_account(
    session: AsyncSession,
    account: Account,
    payload: AccountPatch,
) -> Account:
    if payload.account_name is not None:
        account.account_name = payload.account_name
    if payload.account_handle is not None:
        account.account_handle = payload.account_handle
    if payload.account_signature is not None:
        account.account_signature = payload.account_signature
    if payload.account_type is not None:
        account.account_type = payload.account_type
    if payload.product_code_mode is not None:
        account.product_code_mode = payload.product_code_mode
    if payload.face_mode is not None:
        account.face_mode = payload.face_mode
    if payload.gender is not None:
        account.gender = payload.gender
    if payload.style_description is not None:
        account.style_description = payload.style_description
    if payload.model_appearance is not None:
        account.model_appearance = payload.model_appearance
    if payload.avatar_url is not None:
        account.avatar_url = payload.avatar_url
    if payload.photo_url is not None:
        account.photo_url = payload.photo_url
    if payload.hashtags is not None:
        account.hashtags = payload.hashtags if payload.hashtags else None
    await session.commit()
    await session.refresh(account)
    return account


async def bulk_update_account_attributes(
    session: AsyncSession,
    payload: BulkUpdateAccountAttributesBody,
    owner_id: UUID | None = None,
) -> list[Account]:
    updates = payload.model_dump(exclude={"account_ids"}, exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请至少选择一个要修改的字段",
        )

    # Deduplicate while keeping the client order stable for the response.
    account_ids = list(dict.fromkeys(payload.account_ids))
    stmt = select(Account).where(Account.id.in_(account_ids))
    if owner_id is not None:
        stmt = stmt.where(Account.owner_id == owner_id)

    accounts = list((await session.execute(stmt)).scalars().all())
    if not accounts:
        return []
    account_order = {account_id: index for index, account_id in enumerate(account_ids)}
    accounts.sort(key=lambda account: account_order.get(account.id, len(account_order)))

    for account in accounts:
        for field, value in updates.items():
            setattr(account, field, value)

    await session.commit()
    for account in accounts:
        await session.refresh(account)
    return accounts


async def delete_account(
    session: AsyncSession,
    account_id: UUID,
    owner_id: UUID | None = None,
) -> None:
    await get_account_or_404(session, account_id, owner_id)
    await session.execute(delete(Account).where(Account.id == account_id))
    await session.commit()
