from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenData, get_current_user
from app.db.session import get_db
from app.schemas.account import AccountCreate, AccountListResponse, AccountPatch, AccountRead
from app.services.account_service import (
    create_account,
    delete_account,
    get_account_or_404,
    list_accounts,
    patch_account,
)

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _get_owner_id(current_user: TokenData = Depends(get_current_user)) -> uuid.UUID | None:
    return None if current_user.is_admin else current_user.user_id


@router.post("", response_model=AccountRead, status_code=201)
async def create_account_endpoint(
    payload: AccountCreate,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> AccountRead:
    account = await create_account(session, payload, owner_id)
    return AccountRead.model_validate(account)


@router.get("", response_model=AccountListResponse)
async def list_accounts_endpoint(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> AccountListResponse:
    items, total = await list_accounts(session, page=page, page_size=page_size, owner_id=owner_id)
    return AccountListResponse(
        items=items,  # type: ignore[arg-type]
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
    return AccountRead.model_validate(account)


@router.patch("/{account_id}", response_model=AccountRead)
async def patch_account_endpoint(
    account_id: uuid.UUID,
    payload: AccountPatch,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> AccountRead:
    account = await get_account_or_404(session, account_id, owner_id)
    account = await patch_account(session, account, payload)
    return AccountRead.model_validate(account)


@router.delete("/{account_id}")
async def delete_account_endpoint(
    account_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> Response:
    await delete_account(session, account_id, owner_id)
    return Response(status_code=204)
