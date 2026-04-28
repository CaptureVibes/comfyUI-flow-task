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


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _has_column("video_tasks", "has_face"):
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
    if _has_column("video_tasks", "has_face"):
        op.drop_column("video_tasks", "has_face")
