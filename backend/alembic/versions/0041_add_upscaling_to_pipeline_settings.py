"""add upscaling to pipeline_settings and enum

Revision ID: 0041
Revises: 0040
Create Date: 2026-03-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade():
    # Add upscaling value to VideoAIProcessStatus enum
    op.execute("ALTER TYPE video_ai_process_status ADD VALUE IF NOT EXISTS 'upscaling'")

    # Add upscaling_scale column to pipeline_settings
    op.add_column(
        "pipeline_settings",
        sa.Column("upscaling_scale", sa.Integer(), nullable=False, server_default="1024"),
    )


def downgrade():
    op.drop_column("pipeline_settings", "upscaling_scale")
    # Note: PostgreSQL does not support removing enum values directly
