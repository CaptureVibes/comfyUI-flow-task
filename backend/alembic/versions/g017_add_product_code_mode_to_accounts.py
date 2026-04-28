"""add product_code_mode to accounts

Revision ID: g017_add_product_code_mode
Revises: g016_add_classification_type
Create Date: 2026-04-28
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "g017_add_product_code_mode"
down_revision = "g016_add_classification_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    account_columns = {column["name"] for column in inspector.get_columns("accounts")}

    if "product_code_mode" not in account_columns:
        op.add_column(
            "accounts",
            sa.Column(
                "product_code_mode",
                sa.String(length=20),
                nullable=False,
                server_default="without_code",
            ),
        )
        op.alter_column("accounts", "product_code_mode", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    account_columns = {column["name"] for column in inspector.get_columns("accounts")}

    if "product_code_mode" in account_columns:
        op.drop_column("accounts", "product_code_mode")
