"""add auto_publish fields to video_task_configs

Revision ID: 0052
Revises: 0051
Create Date: 2026-03-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_cols = {c["name"] for c in inspector.get_columns("video_task_configs")}

    if "auto_publish_enabled" not in existing_cols:
        op.add_column("video_task_configs", sa.Column("auto_publish_enabled", sa.Boolean(), nullable=False, server_default="false"))
    if "auto_publish_model" not in existing_cols:
        op.add_column("video_task_configs", sa.Column("auto_publish_model", sa.String(200), nullable=False, server_default="gemini-2.0-flash"))
    if "auto_publish_prompt" not in existing_cols:
        op.add_column("video_task_configs", sa.Column("auto_publish_prompt", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("video_task_configs", "auto_publish_prompt")
    op.drop_column("video_task_configs", "auto_publish_model")
    op.drop_column("video_task_configs", "auto_publish_enabled")
