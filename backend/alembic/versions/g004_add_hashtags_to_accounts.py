"""add hashtags to accounts

Revision ID: g004_add_hashtags_to_accounts
Revises: g003_add_hashtag_search_fields
Create Date: 2026-04-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


revision = "g004_add_hashtags_to_accounts"
down_revision = "g003_add_hashtag_search_fields"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _has_column("accounts", "hashtags"):
        op.add_column("accounts", sa.Column("hashtags", JSON, nullable=True))


def downgrade() -> None:
    if _has_column("accounts", "hashtags"):
        op.drop_column("accounts", "hashtags")
