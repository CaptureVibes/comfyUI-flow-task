"""create tiktok_bloggers table

Revision ID: 0045
Revises: 0044
Create Date: 2026-03-10
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()

    if "tiktok_bloggers" not in existing_tables:
        op.create_table(
            "tiktok_bloggers",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("platform", sa.String(50), nullable=False),
            sa.Column("blogger_id", sa.String(200), nullable=False),
            sa.Column("blogger_name", sa.String(200), nullable=False),
            sa.Column("blogger_handle", sa.String(200), nullable=True),
            sa.Column("blogger_url", sa.Text, nullable=True),
            sa.Column("avatar_url", sa.Text, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint(
                "owner_id", "platform", "blogger_id",
                name="uq_tiktok_bloggers_owner_platform_id",
            ),
        )
        op.create_index("ix_tiktok_bloggers_owner_id", "tiktok_bloggers", ["owner_id"])
        op.create_index("ix_tiktok_bloggers_platform", "tiktok_bloggers", ["platform"])


def downgrade() -> None:
    op.drop_index("ix_tiktok_bloggers_platform", table_name="tiktok_bloggers")
    op.drop_index("ix_tiktok_bloggers_owner_id", table_name="tiktok_bloggers")
    op.drop_table("tiktok_bloggers")
