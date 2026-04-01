"""Service for managing video task pipeline and publish pool configuration."""
from __future__ import annotations

import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.video_task_config import VideoTaskConfig
from app.schemas.video_task_config import VideoTaskConfigRead, VideoTaskConfigUpdate


class VideoTaskConfigService:
    """Per-owner singleton config service."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_config(self, owner_id: uuid.UUID) -> VideoTaskConfig | None:
        """Get config for owner, or None if not exists."""
        return await self.db.get(VideoTaskConfig, owner_id)

    async def upsert_config(
        self, owner_id: uuid.UUID, update: VideoTaskConfigUpdate
    ) -> VideoTaskConfig:
        """Create or update config for owner."""
        config = await self.db.get(VideoTaskConfig, owner_id)

        if config is None:
            config = VideoTaskConfig(owner_id=owner_id)
            self.db.add(config)

        if update.score_threshold_high is not None:
            config.score_threshold_high = update.score_threshold_high
        if update.score_threshold_low is not None:
            config.score_threshold_low = update.score_threshold_low
        if update.pool_ratio is not None:
            config.pool_ratio = update.pool_ratio

        if update.auto_publish_enabled is not None:
            config.auto_publish_enabled = update.auto_publish_enabled
        if update.auto_publish_model is not None:
            config.auto_publish_model = update.auto_publish_model
        if update.auto_publish_prompt is not None:
            config.auto_publish_prompt = update.auto_publish_prompt

        await self.db.flush()
        return config
