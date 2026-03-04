from __future__ import annotations

"""add comment_count to video_sources and video_source_stats

Revision ID: 0021_add_comment_count
Revises: 0020_add_video_source_stats
Create Date: 2026-03-03 00:00:08.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0021_add_comment_count"
down_revision = "0020_add_video_source_stats"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Add to video_sources
    cols_vs = {c["name"] for c in inspector.get_columns("video_sources")}
    if "comment_count" not in cols_vs:
        op.add_column("video_sources", sa.Column("comment_count", sa.Integer(), nullable=True))

    # Add to video_source_stats
    cols_vss = {c["name"] for c in inspector.get_columns("video_source_stats")}
    if "comment_count" not in cols_vss:
        op.add_column("video_source_stats", sa.Column("comment_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    cols_vs = {c["name"] for c in inspector.get_columns("video_sources")}
    if "comment_count" in cols_vs:
        op.drop_column("video_sources", "comment_count")

    cols_vss = {c["name"] for c in inspector.get_columns("video_source_stats")}
    if "comment_count" in cols_vss:
        op.drop_column("video_source_stats", "comment_count")
