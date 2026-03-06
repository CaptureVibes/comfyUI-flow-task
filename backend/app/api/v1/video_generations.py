from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenData, get_current_user
from app.db.session import get_db
from app.schemas.daily_generation import DailyGenerationRead, DailyGenerationStatusUpdate
from app.schemas.video_generation import VideoGenerationRequest
from app.services.video_generation_service import VideoGenerationService

router = APIRouter(prefix="/video-generations", tags=["video-generations"])


def _get_creator_id(current_user: TokenData = Depends(get_current_user)) -> uuid.UUID:
    """For writes: always the actual user_id."""
    return current_user.user_id


def _get_query_owner_id(current_user: TokenData = Depends(get_current_user)) -> uuid.UUID | None:
    """For queries: admin sees all (None = no filter)."""
    return None if current_user.is_admin else current_user.user_id


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def generate_video_endpoint(
    payload: VideoGenerationRequest,
    creator_id: uuid.UUID = Depends(_get_creator_id),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    service = VideoGenerationService(db=session)
    job_id = await service.start_generation(
        account_id=payload.account_id,
        template_id=payload.template_id,
        final_prompt=payload.final_prompt,
        image=payload.image,
        duration=payload.duration,
        shots=payload.shots,
        user_id=creator_id,
    )
    return {"status": "accepted", "job_id": str(job_id)}


@router.get("/daily/{target_date}", response_model=list[DailyGenerationRead])
async def list_daily_jobs_endpoint(
    target_date: date,
    session: AsyncSession = Depends(get_db),
    owner_id: uuid.UUID | None = Depends(_get_query_owner_id),
) -> list[DailyGenerationRead]:
    service = VideoGenerationService(db=session)
    jobs = await service.get_daily_jobs(target_date, owner_id=owner_id)
    return [DailyGenerationRead.model_validate(j) for j in jobs]


@router.post("/daily/{target_date}/upload")
async def upload_daily_jobs_endpoint(
    target_date: date,
    session: AsyncSession = Depends(get_db),
    owner_id: uuid.UUID | None = Depends(_get_query_owner_id),
) -> dict[str, str]:
    service = VideoGenerationService(db=session)
    gcs_url = await service.upload_daily_jobs(target_date, owner_id=owner_id)
    return {"status": "success", "gcs_url": gcs_url}


@router.post("/daily/{target_date}/fetch-results")
async def fetch_daily_results_endpoint(
    target_date: date,
    session: AsyncSession = Depends(get_db),
    owner_id: uuid.UUID | None = Depends(_get_query_owner_id),
) -> dict:
    service = VideoGenerationService(db=session)
    try:
        result = await service.fetch_daily_results(target_date, owner_id=owner_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return result


@router.get("/accounts/{account_id}", response_model=list[DailyGenerationRead])
async def list_account_jobs_endpoint(
    account_id: uuid.UUID,
    status: Optional[str] = Query(None, description="Filter by status"),
    session: AsyncSession = Depends(get_db),
    owner_id: uuid.UUID | None = Depends(_get_query_owner_id),
) -> list[DailyGenerationRead]:
    service = VideoGenerationService(db=session)
    jobs = await service.get_account_jobs(account_id, owner_id=owner_id, status_filter=status)
    return [DailyGenerationRead.model_validate(j) for j in jobs]


@router.patch("/{job_id}/status", response_model=DailyGenerationRead)
async def patch_job_status_endpoint(
    job_id: uuid.UUID,
    body: DailyGenerationStatusUpdate,
    session: AsyncSession = Depends(get_db),
    owner_id: uuid.UUID | None = Depends(_get_query_owner_id),
) -> DailyGenerationRead:
    service = VideoGenerationService(db=session)
    job = await service.patch_status(
        job_id=job_id,
        owner_id=owner_id,
        new_status=body.status,
        result_videos=body.result_videos,
        selected_video_url=body.selected_video_url,
    )
    return DailyGenerationRead.model_validate(job)


@router.post("/{job_id}/rollback", response_model=DailyGenerationRead)
async def rollback_job_status_endpoint(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    owner_id: uuid.UUID | None = Depends(_get_query_owner_id),
) -> DailyGenerationRead:
    service = VideoGenerationService(db=session)
    job = await service.rollback_status(job_id, owner_id=owner_id)
    return DailyGenerationRead.model_validate(job)


@router.delete("/{job_id}")
async def delete_daily_job_endpoint(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    owner_id: uuid.UUID | None = Depends(_get_query_owner_id),
) -> dict[str, str]:
    service = VideoGenerationService(db=session)
    await service.delete_daily_job(job_id, owner_id=owner_id)
    return {"status": "success", "message": "删除成功"}
