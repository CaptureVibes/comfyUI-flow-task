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


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("publish_scheduled_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("accounts", "publish_scheduled_at")
