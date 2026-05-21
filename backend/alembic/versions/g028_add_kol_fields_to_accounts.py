"""add kol_id / kol_user_id / kol_links / kol_provision_status / kol_provision_error to accounts

Revision ID: g028_add_kol_fields
Revises: g027_add_callbacks_log
Create Date: 2026-05-21

Account 创建后会异步去站内平台建对应 KOL（POST /open-api/v1/internal-platform/kol），
然后按平台规则拼长链 → 调短链 encode API，把 kol_id 与每个平台的长/短链都落到 accounts。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "g028_add_kol_fields"
down_revision = "g027_add_callbacks_log"
branch_labels = None
depends_on = None


_NEW_COLUMNS = [
    ("kol_id", sa.Column("kol_id", sa.String(length=64), nullable=True)),
    ("kol_user_id", sa.Column("kol_user_id", sa.String(length=64), nullable=True)),
    ("kol_links", sa.Column("kol_links", sa.JSON(), nullable=True)),
    (
        "kol_provision_status",
        sa.Column(
            "kol_provision_status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
    ),
    ("kol_provision_error", sa.Column("kol_provision_error", sa.Text(), nullable=True)),
]


def upgrade() -> None:
    bind = op.get_bind()
    existing = {c["name"] for c in inspect(bind).get_columns("accounts")}
    for name, column in _NEW_COLUMNS:
        if name not in existing:
            op.add_column("accounts", column)


def downgrade() -> None:
    bind = op.get_bind()
    existing = {c["name"] for c in inspect(bind).get_columns("accounts")}
    # drop in reverse order
    for name, _column in reversed(_NEW_COLUMNS):
        if name in existing:
            op.drop_column("accounts", name)
