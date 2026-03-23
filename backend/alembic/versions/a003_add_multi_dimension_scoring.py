"""Add multi-dimension scoring and critical check fields to video_sub_tasks.

Revision ID: a003_multi_scoring
Revises: a002_mk_gen_status
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa

revision = "a003_multi_scoring"
down_revision = "a002_mk_gen_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Critical check fields (step 3 in user requirements - checked first)
    op.add_column("video_sub_tasks", sa.Column("temporal_consistency", sa.Boolean(), nullable=True))
    op.add_column("video_sub_tasks", sa.Column("character_integrity", sa.Boolean(), nullable=True))
    op.add_column("video_sub_tasks", sa.Column("audio_sync", sa.Boolean(), nullable=True))
    op.add_column("video_sub_tasks", sa.Column("critical_fail", sa.Boolean(), nullable=True))

    # Multi-dimension scoring (step 2 in user requirements)
    # JSON: { "audio_visual": 3, "character_realism": 4, ... }
    op.add_column("video_sub_tasks", sa.Column("dimension_scores", sa.JSON(), nullable=True))
    # Weighted total score (0-100), replaces manual_score
    op.add_column("video_sub_tasks", sa.Column("weighted_total_score", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("video_sub_tasks", "weighted_total_score")
    op.drop_column("video_sub_tasks", "dimension_scores")
    op.drop_column("video_sub_tasks", "critical_fail")
    op.drop_column("video_sub_tasks", "audio_sync")
    op.drop_column("video_sub_tasks", "character_integrity")
    op.drop_column("video_sub_tasks", "temporal_consistency")
