from __future__ import annotations

"""add profile fields to users table

Revision ID: 0013_add_user_profile_fields
Revises: 0012_add_owner_id
Create Date: 2026-03-02 00:00:02.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0013_add_user_profile_fields"
down_revision = "0012_add_owner_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.String(80), nullable=True))
    op.add_column("users", sa.Column("bio", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("avatar_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_url")
    op.drop_column("users", "bio")
    op.drop_column("users", "display_name")
