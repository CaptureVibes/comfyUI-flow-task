"""drop kol_id column from accounts

Revision ID: g029_drop_kol_id
Revises: g028_add_kol_fields
Create Date: 2026-05-21

g028 加的 ``kol_id``（接口 data.id）业务上用不到，统一以 ``kol_user_id``（接口
data.user_id，即长链 ``kolUserId``）作为唯一识别。这里把列删掉，避免后续被误用。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "g029_drop_kol_id"
down_revision = "g028_add_kol_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns("accounts")}
    if "kol_id" in cols:
        op.drop_column("accounts", "kol_id")


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns("accounts")}
    if "kol_id" not in cols:
        op.add_column("accounts", sa.Column("kol_id", sa.String(length=64), nullable=True))
