"""add scheduled publish config to tiktok_bloggers

Revision ID: 0049
Revises: 64b9a8ffd74b
Create Date: 2026-03-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0049"
down_revision = "64b9a8ffd74b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_cols = {c["name"] for c in inspector.get_columns("tiktok_bloggers")}

    if "publish_enabled" not in existing_cols:
        op.add_column("tiktok_bloggers", sa.Column("publish_enabled", sa.Boolean(), nullable=False, server_default="false"))
    if "publish_cron" not in existing_cols:
        op.add_column("tiktok_bloggers", sa.Column("publish_cron", sa.String(100), nullable=True))
    if "publish_window_minutes" not in existing_cols:
        op.add_column("tiktok_bloggers", sa.Column("publish_window_minutes", sa.Integer(), nullable=False, server_default="0"))
    if "publish_count" not in existing_cols:
        op.add_column("tiktok_bloggers", sa.Column("publish_count", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    op.drop_column("tiktok_bloggers", "publish_count")
    op.drop_column("tiktok_bloggers", "publish_window_minutes")
    op.drop_column("tiktok_bloggers", "publish_cron")
    op.drop_column("tiktok_bloggers", "publish_enabled")
