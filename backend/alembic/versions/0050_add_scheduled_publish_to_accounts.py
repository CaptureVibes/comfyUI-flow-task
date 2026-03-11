"""add scheduled publish config to accounts

Revision ID: 0050
Revises: 0049
Create Date: 2026-03-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_cols = {c["name"] for c in inspector.get_columns("accounts")}

    if "publish_enabled" not in existing_cols:
        op.add_column("accounts", sa.Column("publish_enabled", sa.Boolean(), nullable=False, server_default="false"))
    if "publish_cron" not in existing_cols:
        op.add_column("accounts", sa.Column("publish_cron", sa.String(100), nullable=True))
    if "publish_window_minutes" not in existing_cols:
        op.add_column("accounts", sa.Column("publish_window_minutes", sa.Integer(), nullable=False, server_default="0"))
    if "publish_count" not in existing_cols:
        op.add_column("accounts", sa.Column("publish_count", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    op.drop_column("accounts", "publish_count")
    op.drop_column("accounts", "publish_window_minutes")
    op.drop_column("accounts", "publish_cron")
    op.drop_column("accounts", "publish_enabled")
