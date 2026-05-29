"""add hidden to candidate_videos

Revision ID: g038_add_hidden_to_candidate_videos
Revises: g037_add_ai_retry_done
Create Date: 2026-05-29

candidate_videos:
  - hidden (Boolean, default False): 手动隐藏标记，前后端查询均过滤，不影响 status 状态机，可随时恢复。
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "g038_add_hidden_to_candidate_videos"
down_revision = "g037_add_ai_retry_done"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidate_videos",
        sa.Column("hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("candidate_videos", "hidden")
