"""add tiktok_blogger_id to video_sources

Revision ID: 0046
Revises: 0045
Create Date: 2026-03-10
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_cols = [c["name"] for c in inspector.get_columns("video_sources")]

    if "tiktok_blogger_id" not in existing_cols:
        op.add_column(
            "video_sources",
            sa.Column(
                "tiktok_blogger_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey("tiktok_bloggers.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        op.create_index("ix_video_sources_tiktok_blogger_id", "video_sources", ["tiktok_blogger_id"])


def downgrade() -> None:
    op.drop_index("ix_video_sources_tiktok_blogger_id", table_name="video_sources")
    op.drop_column("video_sources", "tiktok_blogger_id")
