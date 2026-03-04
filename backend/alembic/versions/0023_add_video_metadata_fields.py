from __future__ import annotations

"""add video metadata fields to video_sources

Revision ID: 0023_add_video_metadata_fields
Revises: 0022_add_share_count
Create Date: 2026-03-03 08:57:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0023_add_video_metadata_fields"
down_revision = "0022_add_share_count"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Get existing columns
    cols = {c["name"] for c in inspector.get_columns("video_sources")}

    # Add duration field (video duration in seconds)
    if "duration" not in cols:
        op.add_column("video_sources", sa.Column("duration", sa.Integer(), nullable=True, comment="Video duration in seconds"))

    # Add width field (video width in pixels)
    if "width" not in cols:
        op.add_column("video_sources", sa.Column("width", sa.Integer(), nullable=True, comment="Video width in pixels"))

    # Add height field (video height in pixels)
    if "height" not in cols:
        op.add_column("video_sources", sa.Column("height", sa.Integer(), nullable=True, comment="Video height in pixels"))

    # Add aspect_ratio field (video aspect ratio)
    if "aspect_ratio" not in cols:
        op.add_column("video_sources", sa.Column("aspect_ratio", sa.Float(), nullable=True, comment="Video aspect ratio (width/height)"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    cols = {c["name"] for c in inspector.get_columns("video_sources")}

    if "duration" in cols:
        op.drop_column("video_sources", "duration")

    if "width" in cols:
        op.drop_column("video_sources", "width")

    if "height" in cols:
        op.drop_column("video_sources", "height")

    if "aspect_ratio" in cols:
        op.drop_column("video_sources", "aspect_ratio")
