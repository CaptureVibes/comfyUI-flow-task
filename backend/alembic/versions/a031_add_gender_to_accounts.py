"""add gender to accounts

Revision ID: a031_add_gender_to_accounts
Revises: a030_add_face_mode_to_accounts
Create Date: 2026-04-14
"""
import sqlalchemy as sa
from alembic import op

revision = "a031_add_gender_to_accounts"
down_revision = "a030_add_face_mode_to_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("gender", sa.String(20), nullable=False, server_default="female"),
    )


def downgrade() -> None:
    op.drop_column("accounts", "gender")
