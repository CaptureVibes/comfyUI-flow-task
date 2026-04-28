"""add channel_status to account_channel_reservations

Revision ID: g008_channel_status
Revises: g007_channel_fields
Create Date: 2026-04-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "g008_channel_status"
down_revision = "g007_channel_fields"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return (
        table_name in inspector.get_table_names()
        and column_name in {column["name"] for column in inspector.get_columns(table_name)}
    )


def _has_index(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return False
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    if not _has_column("account_channel_reservations", "channel_status"):
        op.add_column(
            "account_channel_reservations",
            sa.Column(
                "channel_status",
                sa.String(length=30),
                nullable=False,
                server_default="active",
            ),
        )
    if not _has_index("account_channel_reservations", "ix_account_channel_reservations_channel_status"):
        op.create_index(
            "ix_account_channel_reservations_channel_status",
            "account_channel_reservations",
            ["channel_status"],
            unique=False,
        )


def downgrade() -> None:
    if _has_index("account_channel_reservations", "ix_account_channel_reservations_channel_status"):
        op.drop_index(
            "ix_account_channel_reservations_channel_status",
            table_name="account_channel_reservations",
        )
    if _has_column("account_channel_reservations", "channel_status"):
        op.drop_column("account_channel_reservations", "channel_status")
