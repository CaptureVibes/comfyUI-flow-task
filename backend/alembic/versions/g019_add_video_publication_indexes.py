"""add indexes on video_publications.completed_at and template_id chain

Revision ID: g019_add_video_publication_indexes
Revises: g018_add_intent_classify
Create Date: 2026-05-06

数据统计列表页 ORDER BY completed_at DESC NULLS LAST + LIMIT/OFFSET 频繁触发，
为该字段加 B-tree 索引避免每次全量排序；同时为 video_ai_templates.video_source_id
加索引（与 video_classifications.video_source_id 配对，用于联表）。
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import inspect


revision = "g019_add_video_publication_indexes"
down_revision = "g018_add_intent_classify"
branch_labels = None
depends_on = None


def _has_index(bind, table: str, name: str) -> bool:
    inspector = inspect(bind)
    return any(idx["name"] == name for idx in inspector.get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_index(bind, "video_publications", "ix_video_publications_completed_at"):
        op.create_index(
            "ix_video_publications_completed_at",
            "video_publications",
            ["completed_at"],
        )
    if not _has_index(bind, "video_ai_templates", "ix_video_ai_templates_video_source_id"):
        op.create_index(
            "ix_video_ai_templates_video_source_id",
            "video_ai_templates",
            ["video_source_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_index(bind, "video_ai_templates", "ix_video_ai_templates_video_source_id"):
        op.drop_index("ix_video_ai_templates_video_source_id", table_name="video_ai_templates")
    if _has_index(bind, "video_publications", "ix_video_publications_completed_at"):
        op.drop_index("ix_video_publications_completed_at", table_name="video_publications")
