"""make tagging callback_url nullable

Revision ID: g047_tagging_callback_nullable
Revises: g046_video_source_persona_tags
Create Date: 2026-06-03

blogger_tagging_results.callback_url 原为 NOT NULL（源自原仓库 webhook 设计），
本项目用内部队列不需要 callback，改为 nullable 以兼容内部调用。
同理 video_tagging_results.callback_url 也一并处理。
"""
from __future__ import annotations

from alembic import op


revision = "g047_tagging_callback_nullable"
down_revision = "g046_video_source_persona_tags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE blogger_tagging_results "
        "ALTER COLUMN callback_url DROP NOT NULL"
    )
    op.execute(
        "ALTER TABLE video_tagging_results "
        "ALTER COLUMN callback_url DROP NOT NULL"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE blogger_tagging_results SET callback_url = '' WHERE callback_url IS NULL"
    )
    op.execute(
        "ALTER TABLE blogger_tagging_results "
        "ALTER COLUMN callback_url SET NOT NULL"
    )
    op.execute(
        "UPDATE video_tagging_results SET callback_url = '' WHERE callback_url IS NULL"
    )
    op.execute(
        "ALTER TABLE video_tagging_results "
        "ALTER COLUMN callback_url SET NOT NULL"
    )
