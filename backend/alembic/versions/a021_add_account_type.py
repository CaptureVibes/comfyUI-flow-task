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


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _has_column("accounts", "account_type"):
        op.add_column(
            "accounts",
            sa.Column("account_type", sa.String(20), nullable=False, server_default="traffic"),
        )


def downgrade() -> None:
    if _has_column("accounts", "account_type"):
        op.drop_column("accounts", "account_type")
