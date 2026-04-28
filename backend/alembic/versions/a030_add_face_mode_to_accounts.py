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


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _has_column("accounts", "face_mode"):
        op.add_column(
            "accounts",
            sa.Column("face_mode", sa.String(20), nullable=False, server_default="face"),
        )


def downgrade() -> None:
    if _has_column("accounts", "face_mode"):
        op.drop_column("accounts", "face_mode")
