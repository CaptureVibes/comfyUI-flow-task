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


def _has_table(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _has_index(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return False
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    if not _has_table("account_channel_reservations"):
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
    for index_name, columns in (
        (op.f("ix_account_channel_reservations_account_id"), ["account_id"]),
        (op.f("ix_account_channel_reservations_platform"), ["platform"]),
        (op.f("ix_account_channel_reservations_status"), ["status"]),
    ):
        if not _has_index("account_channel_reservations", index_name):
            op.create_index(index_name, "account_channel_reservations", columns, unique=False)


def downgrade() -> None:
    if _has_table("account_channel_reservations"):
        for index_name in (
            op.f("ix_account_channel_reservations_status"),
            op.f("ix_account_channel_reservations_platform"),
            op.f("ix_account_channel_reservations_account_id"),
        ):
            if _has_index("account_channel_reservations", index_name):
                op.drop_index(index_name, table_name="account_channel_reservations")
        op.drop_table("account_channel_reservations")
