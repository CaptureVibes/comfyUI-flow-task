"""add is_pinned to flags

Revision ID: 0060
Revises: 0059
Create Date: 2026-04-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("flags")}
    if "is_pinned" not in cols:
        op.add_column(
            "flags",
            sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default="false"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("flags")}
    if "is_pinned" in cols:
        op.drop_column("flags", "is_pinned")
