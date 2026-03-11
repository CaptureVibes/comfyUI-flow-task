"""add publish_last_triggered_at to accounts

Revision ID: 0051
Revises: 0050
Create Date: 2026-03-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_cols = {c["name"] for c in inspector.get_columns("accounts")}
    if "publish_last_triggered_at" not in existing_cols:
        op.add_column(
            "accounts",
            sa.Column("publish_last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("accounts", "publish_last_triggered_at")
