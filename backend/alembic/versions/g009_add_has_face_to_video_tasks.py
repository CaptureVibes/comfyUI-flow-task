"""add has_face to video_tasks

Revision ID: g009_add_has_face
Revises: g008_channel_status
Create Date: 2026-04-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "g009_add_has_face"
down_revision = "g008_channel_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "video_tasks",
        sa.Column(
            "has_face",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("video_tasks", "has_face")
