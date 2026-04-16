from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.flag import AccountFlag
from app.schemas.account import AccountCreate, AccountPatch


async def create_account(
    session: AsyncSession,
    payload: AccountCreate,
    owner_id: UUID | None = None,
) -> Account:
    account = Account(
        owner_id=owner_id,
        account_name=payload.account_name,
        account_type=payload.account_type,
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
) -> tuple[list[Account], int]:
    stmt = select(Account).order_by(Account.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    total_stmt = select(func.count(Account.id))
    if owner_id is not None:
        stmt = stmt.where(Account.owner_id == owner_id)
        total_stmt = total_stmt.where(Account.owner_id == owner_id)
    if flag_id is not None:
        stmt = stmt.where(Account.id.in_(
            select(AccountFlag.account_id).where(AccountFlag.flag_id == flag_id)
        ))
        total_stmt = total_stmt.where(Account.id.in_(
            select(AccountFlag.account_id).where(AccountFlag.flag_id == flag_id)
        ))
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(Account.account_name.ilike(pattern))
        total_stmt = total_stmt.where(Account.account_name.ilike(pattern))
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


async def delete_account(
    session: AsyncSession,
    account_id: UUID,
    owner_id: UUID | None = None,
) -> None:
    await get_account_or_404(session, account_id, owner_id)
    await session.execute(delete(Account).where(Account.id == account_id))
    await session.commit()
