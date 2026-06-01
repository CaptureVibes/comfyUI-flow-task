"""add hidden to accounts

Revision ID: g041_accounts_hidden
Revises: g040_classify_thresh
Create Date: 2026-06-01

accounts:
  - hidden (Boolean, default False, not null): 隐藏标记，True 时不出现在外部分配接口中
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "g041_accounts_hidden"
down_revision = "g040_classify_thresh"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("hidden", sa.Boolean, nullable=False, server_default="false"),
    )
    op.create_index("ix_accounts_hidden", "accounts", ["hidden"])


def downgrade() -> None:
    op.drop_index("ix_accounts_hidden", table_name="accounts")
    op.drop_column("accounts", "hidden")
