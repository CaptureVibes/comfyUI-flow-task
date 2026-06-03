"""add persona tags to video_sources

Revision ID: g046_video_source_persona_tags
Revises: g045_blogger_persona_tags
Create Date: 2026-06-03

在 video_sources 表上新增人设打标回写字段：
  - personal_tags    JSONB  — 单视频 10 维个人标签
  - style_vector     JSONB  — 32 维风格向量
  - tagging_status   VARCHAR — idle | pending | success | failed
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "g046_video_source_persona_tags"
down_revision = "g045_blogger_persona_tags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("video_sources", sa.Column("personal_tags", postgresql.JSONB, nullable=True))
    op.add_column("video_sources", sa.Column("style_vector", postgresql.JSONB, nullable=True))
    op.add_column(
        "video_sources",
        sa.Column("tagging_status", sa.String(20), nullable=False, server_default="idle"),
    )


def downgrade() -> None:
    op.drop_column("video_sources", "tagging_status")
    op.drop_column("video_sources", "style_vector")
    op.drop_column("video_sources", "personal_tags")
