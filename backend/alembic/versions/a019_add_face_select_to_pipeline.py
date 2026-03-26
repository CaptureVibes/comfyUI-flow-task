"""add face_select fields to pipeline_settings

Revision ID: a019_face_select_pipeline
Revises: a018_face_photos
Create Date: 2026-03-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "a019_face_select_pipeline"
down_revision = "a018_face_photos"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pipeline_settings",
        sa.Column("face_select_model", sa.String(200), nullable=False, server_default="gemini-3.1-pro-preview"),
    )
    op.add_column(
        "pipeline_settings",
        sa.Column("face_select_prompt", sa.Text, nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("pipeline_settings", "face_select_prompt")
    op.drop_column("pipeline_settings", "face_select_model")
