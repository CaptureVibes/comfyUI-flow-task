"""add publish_scheduled_at to accounts

Revision ID: g010_publish_scheduled_at
Revises: g009_add_has_face
Create Date: 2026-04-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "g010_publish_scheduled_at"
down_revision = "g009_add_has_face"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _has_column("accounts", "publish_scheduled_at"):
        op.add_column(
            "accounts",
            sa.Column("publish_scheduled_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    if _has_column("accounts", "publish_scheduled_at"):
        op.drop_column("accounts", "publish_scheduled_at")
