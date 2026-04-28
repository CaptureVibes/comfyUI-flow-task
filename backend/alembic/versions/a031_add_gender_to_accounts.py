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


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _has_column("accounts", "gender"):
        op.add_column(
            "accounts",
            sa.Column("gender", sa.String(20), nullable=False, server_default="female"),
        )


def downgrade() -> None:
    if _has_column("accounts", "gender"):
        op.drop_column("accounts", "gender")
