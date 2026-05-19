"""add sub_task_success_sample_size to pipeline_settings

Revision ID: g024_add_sub_task_success_sample
Revises: g023_add_formal_backfill
Create Date: 2026-05-19

「最近 N 条子任务成功率」公式里 N 的配置项，默认 10。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "g024_add_sub_task_success_sample"
down_revision = "g023_add_formal_backfill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {col["name"] for col in inspector.get_columns("pipeline_settings")}
    if "sub_task_success_sample_size" in existing:
        return
    op.add_column(
        "pipeline_settings",
        sa.Column(
            "sub_task_success_sample_size",
            sa.Integer(),
            nullable=False,
            server_default="10",
        ),
    )
    op.alter_column("pipeline_settings", "sub_task_success_sample_size", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {col["name"] for col in inspector.get_columns("pipeline_settings")}
    if "sub_task_success_sample_size" in existing:
        op.drop_column("pipeline_settings", "sub_task_success_sample_size")
