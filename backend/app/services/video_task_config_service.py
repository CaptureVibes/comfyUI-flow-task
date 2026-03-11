"""Service for managing video task AI scoring configuration."""
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
            # Create new with defaults merged with updates
            config = VideoTaskConfig(owner_id=owner_id)
            self.db.add(config)

        # Apply non-None updates
        if update.round1_enabled is not None:
            config.round1_enabled = update.round1_enabled
        if update.round1_prompt is not None:
            config.round1_prompt = update.round1_prompt
        if update.round1_model is not None:
            config.round1_model = update.round1_model
        if update.round1_threshold is not None:
            config.round1_threshold = update.round1_threshold
        if update.round1_weight is not None:
            config.round1_weight = update.round1_weight

        if update.round2_enabled is not None:
            config.round2_enabled = update.round2_enabled
        if update.round2_prompt is not None:
            config.round2_prompt = update.round2_prompt
        if update.round2_model is not None:
            config.round2_model = update.round2_model
        if update.round2_threshold is not None:
            config.round2_threshold = update.round2_threshold
        if update.round2_weight is not None:
            config.round2_weight = update.round2_weight

        if update.final_threshold is not None:
            config.final_threshold = update.final_threshold

        if update.auto_publish_enabled is not None:
            config.auto_publish_enabled = update.auto_publish_enabled
        if update.auto_publish_model is not None:
            config.auto_publish_model = update.auto_publish_model
        if update.auto_publish_prompt is not None:
            config.auto_publish_prompt = update.auto_publish_prompt

        await self.db.flush()
        return config
