"""drop ai_account_photo_video_prompt from pipeline_settings

Revision ID: a020_drop_photo_video_prompt
Revises: a019_face_select_pipeline
Create Date: 2026-03-26
"""
from alembic import op

revision = "a020_drop_photo_video_prompt"
down_revision = "a019_face_select_pipeline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("pipeline_settings", "ai_account_photo_video_prompt")


def downgrade() -> None:
    import sqlalchemy as sa
    op.add_column(
        "pipeline_settings",
        sa.Column("ai_account_photo_video_prompt", sa.Text(), nullable=False, server_default=""),
    )
