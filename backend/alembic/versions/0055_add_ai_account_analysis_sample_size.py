"""add ai account analysis sample size and widen status

Revision ID: 0055
Revises: 0054
Create Date: 2026-03-13
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    pipeline_cols = {c["name"] for c in inspector.get_columns("pipeline_settings")}
    if "ai_account_analysis_sample_size" not in pipeline_cols:
        op.add_column(
            "pipeline_settings",
            sa.Column(
                "ai_account_analysis_sample_size",
                sa.Integer(),
                nullable=False,
                server_default="10",
            ),
        )

    op.alter_column(
        "accounts",
        "ai_generation_status",
        existing_type=sa.String(length=20),
        type_=sa.String(length=40),
        existing_nullable=False,
        existing_server_default="idle",
    )


def downgrade() -> None:
    op.alter_column(
        "accounts",
        "ai_generation_status",
        existing_type=sa.String(length=40),
        type_=sa.String(length=20),
        existing_nullable=False,
        existing_server_default="idle",
    )
    op.drop_column("pipeline_settings", "ai_account_analysis_sample_size")
