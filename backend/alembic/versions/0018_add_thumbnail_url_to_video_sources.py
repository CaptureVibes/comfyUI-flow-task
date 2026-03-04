from __future__ import annotations

"""add thumbnail_url to video_sources

Revision ID: 0018_add_thumbnail_url
Revises: 0017_add_evolink_settings
Create Date: 2026-03-03 00:00:05.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0018_add_thumbnail_url"
down_revision = "0017_add_evolink_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("video_sources")}
    if "thumbnail_url" not in cols:
        op.add_column("video_sources", sa.Column("thumbnail_url", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("video_sources")}
    if "thumbnail_url" in cols:
        op.drop_column("video_sources", "thumbnail_url")
