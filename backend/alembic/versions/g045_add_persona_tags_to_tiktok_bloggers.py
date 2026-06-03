"""add persona tags to tiktok_bloggers

Revision ID: g045_blogger_persona_tags
Revises: g044_persona_tagging
Create Date: 2026-06-03

在 tiktok_bloggers 表上新增人设打标回写字段：
  - persona_tags       JSONB  — 账号级人设标签（basic_demographics, consumption_tier 等）
  - style_vector       JSONB  — 32 维风格向量均值
  - style_signature    JSONB  — 8-facet 账号级风格签名
  - tagging_status     VARCHAR — idle | pending | success | failed
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "g045_blogger_persona_tags"
down_revision = "g044_persona_tagging"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE tiktok_bloggers ADD COLUMN IF NOT EXISTS persona_tags JSONB")
    op.execute("ALTER TABLE tiktok_bloggers ADD COLUMN IF NOT EXISTS style_vector JSONB")
    op.execute("ALTER TABLE tiktok_bloggers ADD COLUMN IF NOT EXISTS style_signature JSONB")
    op.execute("ALTER TABLE tiktok_bloggers ADD COLUMN IF NOT EXISTS tagging_status VARCHAR(20) NOT NULL DEFAULT 'idle'")


def downgrade() -> None:
    op.drop_column("tiktok_bloggers", "tagging_status")
    op.drop_column("tiktok_bloggers", "style_signature")
    op.drop_column("tiktok_bloggers", "style_vector")
    op.drop_column("tiktok_bloggers", "persona_tags")
