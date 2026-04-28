"""drop ai_account_photo_video_prompt from pipeline_settings

Revision ID: a020_drop_photo_video_prompt
Revises: a019_face_select_pipeline
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa

revision = "a020_drop_photo_video_prompt"
down_revision = "a019_face_select_pipeline"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if _has_column("pipeline_settings", "ai_account_photo_video_prompt"):
        op.drop_column("pipeline_settings", "ai_account_photo_video_prompt")


def downgrade() -> None:
    if not _has_column("pipeline_settings", "ai_account_photo_video_prompt"):
        op.add_column(
            "pipeline_settings",
            sa.Column("ai_account_photo_video_prompt", sa.Text(), nullable=False, server_default=""),
        )
