"""add flags and account_flags tables

Revision ID: 0059
Revises: 0058
Create Date: 2026-04-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "flags" not in existing_tables:
        op.create_table(
            "flags",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("color", sa.String(20), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    existing_indexes = {idx["name"] for idx in inspector.get_indexes("flags")} if "flags" in existing_tables else set()
    if "ix_flags_owner_id" not in existing_indexes:
        op.create_index("ix_flags_owner_id", "flags", ["owner_id"])

    if "account_flags" not in existing_tables:
        op.create_table(
            "account_flags",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "account_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("accounts.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "flag_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("flags.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("account_id", "flag_id", name="uq_account_flags"),
        )

    af_indexes = {idx["name"] for idx in inspector.get_indexes("account_flags")} if "account_flags" in existing_tables else set()
    if "ix_account_flags_account_id" not in af_indexes:
        op.create_index("ix_account_flags_account_id", "account_flags", ["account_id"])
    if "ix_account_flags_flag_id" not in af_indexes:
        op.create_index("ix_account_flags_flag_id", "account_flags", ["flag_id"])


def downgrade() -> None:
    op.drop_table("account_flags")
    op.drop_table("flags")
