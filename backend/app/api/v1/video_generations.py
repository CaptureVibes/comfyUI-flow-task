from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenData, get_current_user
from app.db.session import get_db
from app.schemas.video_generation import VideoGenerationRequest
from app.services.video_generation_service import VideoGenerationService

router = APIRouter(prefix="/video-generations", tags=["video-generations"])

def _get_creator_id(current_user: TokenData = Depends(get_current_user)) -> uuid.UUID:
    """Create records: always returns actual user_id"""
    return current_user.user_id

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
        user_id=creator_id
    )
    return {"status": "accepted", "job_id": str(job_id)}
