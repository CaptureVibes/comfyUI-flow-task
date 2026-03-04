from __future__ import annotations

"""add video_sources table

Revision ID: 0014_add_video_sources
Revises: 0013_add_user_profile_fields
Create Date: 2026-03-03 00:00:01.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0014_add_video_sources"
down_revision = "0013_add_user_profile_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "video_sources" in existing_tables:
        return
    op.create_table(
        "video_sources",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("platform", sa.String(50), nullable=True),
        sa.Column("blogger_name", sa.String(200), nullable=True),
        sa.Column("video_title", sa.String(500), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("video_url", sa.Text(), nullable=True),
        sa.Column("view_count", sa.Integer(), nullable=True),
        sa.Column("like_count", sa.Integer(), nullable=True),
        sa.Column("favorite_count", sa.Integer(), nullable=True),
        sa.Column("publish_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extra", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "video_sources" in set(inspector.get_table_names()):
        op.drop_table("video_sources")
