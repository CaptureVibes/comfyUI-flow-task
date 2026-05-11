"""临时需求：正式号回填 API。

仅 admin 可访问。提供生成 / 清空 / 查询 / 导出四个端点，前端用一个独立页面驱动。
"""
from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenData, get_current_user
from app.db.session import get_db
from app.services.formal_backfill_service import (
    clear_plan,
    export_task_ids,
    generate_plan,
    get_summary,
)

router = APIRouter(prefix="/formal-backfill", tags=["formal-backfill"])
logger = logging.getLogger("app.formal_backfill")


def _require_admin(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user


class GeneratePlanBody(BaseModel):
    target_total: int = Field(..., ge=1, le=10000, description="今天应该达到的正式号总数")
    start_date: date
    end_date: date
    seed: int | None = Field(default=None, description="随机种子（可选，便于复现）")


class GeneratePlanResponse(BaseModel):
    target_total: int
    actual_total: int
    start_date: date
    end_date: date
    daily_counts: list[dict]


@router.post("/generate", response_model=GeneratePlanResponse)
async def generate_formal_backfill(
    body: GeneratePlanBody,
    _: TokenData = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> GeneratePlanResponse:
    if body.end_date < body.start_date:
        raise HTTPException(status_code=422, detail="end_date 不能早于 start_date")
    result = await generate_plan(
        session,
        target_total=body.target_total,
        start_date=body.start_date,
        end_date=body.end_date,
        seed=body.seed,
    )
    return GeneratePlanResponse(
        target_total=result.target_total,
        actual_total=result.actual_total,
        start_date=result.start_date,
        end_date=result.end_date,
        daily_counts=result.daily_counts,
    )


@router.delete("")
async def clear_formal_backfill(
    _: TokenData = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> dict:
    deleted = await clear_plan(session)
    return {"deleted": deleted}


@router.get("/summary")
async def get_formal_backfill_summary(
    _: TokenData = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> dict:
    return await get_summary(session)


@router.get("/export")
async def export_formal_backfill(
    _: TokenData = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> dict:
    task_ids = await export_task_ids(session)
    return {"total": len(task_ids), "task_ids": task_ids}
