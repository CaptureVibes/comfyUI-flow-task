from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenData, get_current_user
from app.db.session import get_db
from app.models.flag import AccountFlag, Flag

router = APIRouter(prefix="/flags", tags=["flags"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class FlagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str | None = None
    is_pinned: bool = False


class FlagPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    color: str | None = None
    is_pinned: bool | None = None


class FlagRead(BaseModel):
    id: uuid.UUID
    name: str
    color: str | None
    is_pinned: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class BulkBindFlagsBody(BaseModel):
    account_ids: list[uuid.UUID]
    flag_ids: list[uuid.UUID]


class BulkUnbindFlagsBody(BaseModel):
    account_ids: list[uuid.UUID]
    flag_ids: list[uuid.UUID]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _owner_id(current_user: TokenData = Depends(get_current_user)) -> uuid.UUID | None:
    return None if current_user.is_admin else current_user.user_id


def _creator_id(current_user: TokenData = Depends(get_current_user)) -> uuid.UUID:
    return current_user.user_id


# ── Flag CRUD ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[FlagRead])
async def list_flags(
    owner_id: uuid.UUID | None = Depends(_owner_id),
    session: AsyncSession = Depends(get_db),
) -> list[FlagRead]:
    # 快捷标签排在前面，其余按创建时间排
    stmt = select(Flag).order_by(Flag.is_pinned.desc(), Flag.created_at.asc())
    if owner_id is not None:
        stmt = stmt.where(Flag.owner_id == owner_id)
    rows = (await session.execute(stmt)).scalars().all()
    return [FlagRead.model_validate(f) for f in rows]


@router.post("", response_model=FlagRead, status_code=201)
async def create_flag(
    payload: FlagCreate,
    creator_id: uuid.UUID = Depends(_creator_id),
    session: AsyncSession = Depends(get_db),
) -> FlagRead:
    flag = Flag(
        owner_id=creator_id,
        name=payload.name,
        color=payload.color,
        is_pinned=payload.is_pinned,
        created_at=datetime.now(timezone.utc),
    )
    session.add(flag)
    await session.commit()
    await session.refresh(flag)
    return FlagRead.model_validate(flag)


@router.patch("/{flag_id}", response_model=FlagRead)
async def patch_flag(
    flag_id: uuid.UUID,
    payload: FlagPatch,
    owner_id: uuid.UUID | None = Depends(_owner_id),
    session: AsyncSession = Depends(get_db),
) -> FlagRead:
    flag = await session.get(Flag, flag_id)
    if not flag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标识不存在")
    if owner_id is not None and flag.owner_id != owner_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")
    if payload.name is not None:
        flag.name = payload.name
    if payload.color is not None:
        flag.color = payload.color
    if payload.is_pinned is not None:
        flag.is_pinned = payload.is_pinned
    await session.commit()
    await session.refresh(flag)
    return FlagRead.model_validate(flag)


@router.delete("/{flag_id}")
async def delete_flag(
    flag_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_owner_id),
    session: AsyncSession = Depends(get_db),
) -> Response:
    flag = await session.get(Flag, flag_id)
    if not flag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标识不存在")
    if owner_id is not None and flag.owner_id != owner_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")
    await session.delete(flag)
    await session.commit()
    return Response(status_code=204)


# ── 批量绑定 / 解绑 ───────────────────────────────────────────────────────────

@router.post("/bulk-bind", status_code=200)
async def bulk_bind_flags(
    body: BulkBindFlagsBody,
    owner_id: uuid.UUID | None = Depends(_owner_id),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """批量给多个账号绑定多个标识"""
    if not body.account_ids or not body.flag_ids:
        return {"status": "ok", "bound": 0}

    for flag_id in body.flag_ids:
        flag = await session.get(Flag, flag_id)
        if not flag:
            raise HTTPException(status_code=404, detail=f"标识 {flag_id} 不存在")

    bound = 0
    for account_id in body.account_ids:
        for flag_id in body.flag_ids:
            existing = await session.scalar(
                select(AccountFlag)
                .where(AccountFlag.account_id == account_id)
                .where(AccountFlag.flag_id == flag_id)
            )
            if not existing:
                session.add(AccountFlag(
                    account_id=account_id,
                    flag_id=flag_id,
                    created_at=datetime.now(timezone.utc),
                ))
                bound += 1
    await session.commit()
    return {"status": "ok", "bound": bound}


@router.post("/bulk-unbind", status_code=200)
async def bulk_unbind_flags(
    body: BulkUnbindFlagsBody,
    owner_id: uuid.UUID | None = Depends(_owner_id),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """批量从多个账号移除多个标识"""
    if not body.account_ids or not body.flag_ids:
        return {"status": "ok", "removed": 0}

    stmt = (
        select(AccountFlag)
        .where(AccountFlag.account_id.in_(body.account_ids))
        .where(AccountFlag.flag_id.in_(body.flag_ids))
    )
    rows = (await session.execute(stmt)).scalars().all()
    for row in rows:
        await session.delete(row)
    await session.commit()
    return {"status": "ok", "removed": len(rows)}
