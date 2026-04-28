"""add classification_type to accounts

Revision ID: g016_add_classification_type
Revises: g015_classify_thresholds
Create Date: 2026-04-27
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine.reflection import Inspector


revision = "g016_add_classification_type"
down_revision = "g015_classify_thresholds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    account_columns = {c["name"] for c in inspector.get_columns("accounts")}
    indexes = {i["name"] for i in inspector.get_indexes("accounts")}

    if "classification_type" not in account_columns:
        op.add_column(
            "accounts",
            sa.Column("classification_type", sa.String(length=20), nullable=True),
        )
    if "idx_accounts_classification_type" not in indexes:
        op.create_index(
            "idx_accounts_classification_type",
            "accounts",
            ["classification_type"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    indexes = {i["name"] for i in inspector.get_indexes("accounts")}
    account_columns = {c["name"] for c in inspector.get_columns("accounts")}

    if "idx_accounts_classification_type" in indexes:
        op.drop_index("idx_accounts_classification_type", table_name="accounts")
    if "classification_type" in account_columns:
        op.drop_column("accounts", "classification_type")
