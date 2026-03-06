"""add is_used to video_ai_templates

Revision ID: 0040
Revises: 0039
Create Date: 2026-03-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "video_ai_templates",
        sa.Column("is_used", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_column("video_ai_templates", "is_used")
