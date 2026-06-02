"""add ai_retry_done to video_tasks

Revision ID: g037_add_ai_retry_done
Revises: g036_add_business_context
Create Date: 2026-05-28

video_tasks:
  - ai_retry_done (Boolean, default False): AI 模板成功写回 shots 后标记为 True，
    一键重试时跳过已处理完成的任务，防止重复触发。
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "g037_add_ai_retry_done"
down_revision = "g036_add_business_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "video_tasks",
        sa.Column("ai_retry_done", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("video_tasks", "ai_retry_done")
