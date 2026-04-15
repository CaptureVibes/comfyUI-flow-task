"""add account channel reservations

Revision ID: g005_channel_reservations
Revises: g004_add_hashtags_to_accounts
Create Date: 2026-04-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "g005_channel_reservations"
down_revision = "g004_add_hashtags_to_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_channel_reservations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="reserved"),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="openapi"),
        sa.Column("channel_info", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bound_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "platform", name="uq_account_channel_reservations_account_platform"),
    )
    op.create_index(
        op.f("ix_account_channel_reservations_account_id"),
        "account_channel_reservations",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_account_channel_reservations_platform"),
        "account_channel_reservations",
        ["platform"],
        unique=False,
    )
    op.create_index(
        op.f("ix_account_channel_reservations_status"),
        "account_channel_reservations",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_account_channel_reservations_status"), table_name="account_channel_reservations")
    op.drop_index(op.f("ix_account_channel_reservations_platform"), table_name="account_channel_reservations")
    op.drop_index(op.f("ix_account_channel_reservations_account_id"), table_name="account_channel_reservations")
    op.drop_table("account_channel_reservations")
