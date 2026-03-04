from __future__ import annotations

"""add video_desc field to video_sources

Revision ID: 0024_add_video_desc_field
Revises: 0023_add_video_metadata_fields
Create Date: 2026-03-03 17:20:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0024_add_video_desc_field"
down_revision = "0023_add_video_metadata_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Get existing columns
    cols = {c["name"] for c in inspector.get_columns("video_sources")}

    # Add video_desc field
    if "video_desc" not in cols:
        op.add_column("video_sources", sa.Column("video_desc", sa.Text(), nullable=True, comment="Video description"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    cols = {c["name"] for c in inspector.get_columns("video_sources")}

    if "video_desc" in cols:
        op.drop_column("video_sources", "video_desc")
