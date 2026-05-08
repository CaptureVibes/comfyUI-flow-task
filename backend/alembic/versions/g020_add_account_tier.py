"""add account_tier to accounts

Revision ID: g020_add_account_tier
Revises: g019_pub_stats_indexes
Create Date: 2026-05-08

为账号增加分级字段：test=实验号(默认)、dev=常规号、prod=正式号。
默认所有账号均为 test，由 account_tier_scheduler 按规则晋级。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "g020_add_account_tier"
down_revision = "g019_pub_stats_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    account_columns = {column["name"] for column in inspector.get_columns("accounts")}

    if "account_tier" not in account_columns:
        op.add_column(
            "accounts",
            sa.Column(
                "account_tier",
                sa.String(length=20),
                nullable=False,
                server_default="test",
            ),
        )
        op.alter_column("accounts", "account_tier", server_default=None)
        op.create_index(
            "ix_accounts_account_tier",
            "accounts",
            ["account_tier"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    account_columns = {column["name"] for column in inspector.get_columns("accounts")}

    if "account_tier" in account_columns:
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("accounts")}
        if "ix_accounts_account_tier" in existing_indexes:
            op.drop_index("ix_accounts_account_tier", table_name="accounts")
        op.drop_column("accounts", "account_tier")
