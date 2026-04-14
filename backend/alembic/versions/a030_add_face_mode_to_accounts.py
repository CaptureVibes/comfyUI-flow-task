"""add face_mode to accounts

Revision ID: a030_add_face_mode_to_accounts
Revises: a1b2c3d4e5f6
Create Date: 2026-04-14
"""
import sqlalchemy as sa
from alembic import op

revision = "a030_add_face_mode_to_accounts"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("face_mode", sa.String(20), nullable=False, server_default="face"),
    )


def downgrade() -> None:
    op.drop_column("accounts", "face_mode")
