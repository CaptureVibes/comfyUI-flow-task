"""add performance_snapshot to accounts

Revision ID: 0057
Revises: 0056
Create Date: 2026-04-03
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("accounts")}
    if "performance_snapshot" not in columns:
        op.add_column("accounts", sa.Column("performance_snapshot", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("accounts")}
    if "performance_snapshot" in columns:
        op.drop_column("accounts", "performance_snapshot")
