"""add face_removing settings to pipeline_settings

Revision ID: 0039
Revises: 0038
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pipeline_settings",
        sa.Column("face_removing_api_url", sa.String(500), nullable=False, server_default="http://34.86.216.234:8001"),
    )
    op.add_column(
        "pipeline_settings",
        sa.Column("face_removing_score_thresh", sa.Float(), nullable=False, server_default="0.3"),
    )
    op.add_column(
        "pipeline_settings",
        sa.Column("face_removing_margin_scale", sa.Float(), nullable=False, server_default="0.2"),
    )
    op.add_column(
        "pipeline_settings",
        sa.Column("face_removing_head_top_ratio", sa.Float(), nullable=False, server_default="0.7"),
    )


def downgrade() -> None:
    op.drop_column("pipeline_settings", "face_removing_head_top_ratio")
    op.drop_column("pipeline_settings", "face_removing_margin_scale")
    op.drop_column("pipeline_settings", "face_removing_score_thresh")
    op.drop_column("pipeline_settings", "face_removing_api_url")
