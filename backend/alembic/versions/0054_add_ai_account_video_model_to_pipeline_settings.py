"""add missing ai_account_video_model to pipeline_settings

Revision ID: 0054
Revises: 0053_ai_account
Create Date: 2026-03-12
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "0054"
down_revision = "0053_ai_account"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_cols = {c["name"] for c in inspector.get_columns("pipeline_settings")}

    if "ai_account_video_model" not in existing_cols:
        op.add_column(
            "pipeline_settings",
            sa.Column(
                "ai_account_video_model",
                sa.String(length=200),
                nullable=False,
                server_default="gemini-3.1-pro-preview",
            ),
        )


def downgrade() -> None:
    op.drop_column("pipeline_settings", "ai_account_video_model")
