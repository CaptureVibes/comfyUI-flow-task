"""add rejected_videos column to external_supplement_requests

Revision ID: g026_add_rejected_videos
Revises: g025_add_ext_supplement
Create Date: 2026-05-20

记录 vendor 回调中 AI 审核 / 分类未通过的视频明细，便于每次 request 事后查看：
  rejected_videos JSON NOT NULL DEFAULT '[]'
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "g026_add_rejected_videos"
down_revision = "g025_add_ext_supplement"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns("external_supplement_requests")}
    if "rejected_videos" not in cols:
        op.add_column(
            "external_supplement_requests",
            sa.Column(
                "rejected_videos",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'::json"),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns("external_supplement_requests")}
    if "rejected_videos" in cols:
        op.drop_column("external_supplement_requests", "rejected_videos")
