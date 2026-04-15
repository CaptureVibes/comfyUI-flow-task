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


def upgrade() -> None:
    op.add_column("accounts", sa.Column("hashtags", JSON, nullable=True))


def downgrade() -> None:
    op.drop_column("accounts", "hashtags")
