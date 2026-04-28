"""add is_prompt_updated to video_tasks

Revision ID: a023_add_is_prompt_updated
Revises: a022_add_painting_prompt
Create Date: 2026-03-30
"""
import sqlalchemy as sa
from alembic import op

revision = "a023_add_is_prompt_updated"
down_revision = "a022_add_painting_prompt"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _has_column("video_tasks", "is_prompt_updated"):
        op.add_column(
            "video_tasks",
            sa.Column("is_prompt_updated", sa.Boolean(), nullable=False, server_default="false"),
        )


def downgrade() -> None:
    if _has_column("video_tasks", "is_prompt_updated"):
        op.drop_column("video_tasks", "is_prompt_updated")
