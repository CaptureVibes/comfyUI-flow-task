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


def upgrade() -> None:
    op.add_column(
        "account_channel_reservations",
        sa.Column(
            "channel_status",
            sa.String(length=30),
            nullable=False,
            server_default="active",
        ),
    )
    op.create_index(
        "ix_account_channel_reservations_channel_status",
        "account_channel_reservations",
        ["channel_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_account_channel_reservations_channel_status",
        table_name="account_channel_reservations",
    )
    op.drop_column("account_channel_reservations", "channel_status")
