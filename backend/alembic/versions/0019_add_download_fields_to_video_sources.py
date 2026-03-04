from __future__ import annotations

"""add download_status and local_video_url to video_sources

Revision ID: 0019_add_download_fields
Revises: 0018_add_thumbnail_url
Create Date: 2026-03-03 00:00:06.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0019_add_download_fields"
down_revision = "0018_add_thumbnail_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("video_sources")}
    if "local_video_url" not in cols:
        op.add_column("video_sources", sa.Column("local_video_url", sa.Text(), nullable=True))
    if "download_status" not in cols:
        op.add_column(
            "video_sources",
            sa.Column("download_status", sa.String(20), nullable=True, server_default="idle"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("video_sources")}
    if "local_video_url" in cols:
        op.drop_column("video_sources", "local_video_url")
    if "download_status" in cols:
        op.drop_column("video_sources", "download_status")
