from __future__ import annotations

"""add video_source_stats table

Revision ID: 0020_add_video_source_stats
Revises: 0019_add_download_fields
Create Date: 2026-03-03 00:00:07.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0020_add_video_source_stats"
down_revision = "0019_add_download_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "video_source_stats" not in inspector.get_table_names():
        op.create_table(
            "video_source_stats",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column("video_source_id", sa.Uuid(as_uuid=True), nullable=False),
            sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("view_count", sa.Integer(), nullable=True),
            sa.Column("like_count", sa.Integer(), nullable=True),
            sa.Column("favorite_count", sa.Integer(), nullable=True),
        )
        op.create_index("ix_video_source_stats_vs_id", "video_source_stats", ["video_source_id"])
        op.create_index("ix_video_source_stats_collected_at", "video_source_stats", ["collected_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "video_source_stats" in inspector.get_table_names():
        op.drop_index("ix_video_source_stats_collected_at", table_name="video_source_stats")
        op.drop_index("ix_video_source_stats_vs_id", table_name="video_source_stats")
        op.drop_table("video_source_stats")
