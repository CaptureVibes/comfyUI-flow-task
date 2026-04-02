"""API endpoints for video task pipeline and publish pool configuration."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import TokenData, get_current_user
from app.db.session import get_db
from app.schemas.video_task_config import VideoTaskConfigRead, VideoTaskConfigUpdate
from app.services.video_task_config_service import VideoTaskConfigService
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


def _config_to_dict(config) -> dict:
    """Convert ORM object to dict for response."""
    if config is None:
        return {}
    return {
        "top_percent": config.top_percent,
        "discard_below": config.discard_below,
        "select_percent": config.select_percent,
        "auto_publish_enabled": config.auto_publish_enabled,
        "auto_publish_model": config.auto_publish_model,
        "auto_publish_prompt": config.auto_publish_prompt,
    }


@router.get("/video-task-config", response_model=VideoTaskConfigRead)
async def get_video_task_config(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VideoTaskConfigRead:
    """Get video task pipeline config for current user."""
    svc = VideoTaskConfigService(db)
    config = await svc.get_config(current_user.user_id)

    if config is None:
        return VideoTaskConfigRead()

    return VideoTaskConfigRead(**_config_to_dict(config))


@router.put("/video-task-config", response_model=VideoTaskConfigRead)
async def update_video_task_config(
    update: VideoTaskConfigUpdate,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VideoTaskConfigRead:
    """Update (or create) video task pipeline config for current user."""
    svc = VideoTaskConfigService(db)
    config = await svc.upsert_config(current_user.user_id, update)
    await db.commit()

    return VideoTaskConfigRead(**_config_to_dict(config))
