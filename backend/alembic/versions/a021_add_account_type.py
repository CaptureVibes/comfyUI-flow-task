"""add account_type to accounts

Revision ID: a021_add_account_type
Revises: a020_drop_photo_video_prompt
Create Date: 2026-03-27
"""
import sqlalchemy as sa
from alembic import op

revision = "a021_add_account_type"
down_revision = "a020_drop_photo_video_prompt"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("account_type", sa.String(20), nullable=False, server_default="traffic"),
    )


def downgrade() -> None:
    op.drop_column("accounts", "account_type")
