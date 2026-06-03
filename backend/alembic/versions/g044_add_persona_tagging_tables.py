"""add persona tagging tables

Revision ID: g044_persona_tagging
Revises: g043_kol_clicks_indexes
Create Date: 2026-06-03

新增两张表用于 TikTok 博主/视频的人设打标（persona-layer-tagging）：
  - video_tagging_results：单视频打标任务及结果
  - blogger_tagging_results：博主账号级打标任务及聚合结果
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "g044_persona_tagging"
down_revision = "g043_kol_clicks_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "video_tagging_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("gcs_url", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("result_code", sa.Integer, nullable=True),
        sa.Column("result_message", sa.Text, nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("video_description_unit", postgresql.JSONB, nullable=True),
        sa.Column("personal_tags", postgresql.JSONB, nullable=True),
        sa.Column("style_vector", postgresql.JSONB, nullable=True),
        sa.Column("style_signature", postgresql.JSONB, nullable=True),
        sa.Column("raw_outputs", postgresql.JSONB, nullable=True),
        sa.Column("source_type", sa.String(50), nullable=False, server_default="direct"),
        sa.Column("source_blogger_task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_tiktok_blogger_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("worker_id", sa.String(200), nullable=True),
        sa.Column("lock_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_video_tagging_results_video_id", "video_tagging_results", ["video_id"])
    op.create_index("ix_video_tagging_results_status", "video_tagging_results", ["status"])
    op.create_index("ix_video_tagging_results_source_blogger", "video_tagging_results", ["source_tiktok_blogger_id"])

    op.create_table(
        "blogger_tagging_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tiktok_blogger_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("result_code", sa.Integer, nullable=True),
        sa.Column("result_message", sa.Text, nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("min_video_count", sa.Integer, nullable=False, server_default="15"),
        sa.Column("available_video_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("usable_video_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("successful_video_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed_video_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("submitted_video_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("selected_video_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        sa.Column("video_task_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        sa.Column("account_personal_tags", postgresql.JSONB, nullable=True),
        sa.Column("account_style_vector", postgresql.JSONB, nullable=True),
        sa.Column("account_style_signature", postgresql.JSONB, nullable=True),
        sa.Column("aggregated_social_identity", postgresql.JSONB, nullable=True),
        sa.Column("aggregated_occasion", postgresql.JSONB, nullable=True),
        sa.Column("raw_outputs", postgresql.JSONB, nullable=True),
        sa.Column("worker_id", sa.String(200), nullable=True),
        sa.Column("lock_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_blogger_tagging_results_blogger_id", "blogger_tagging_results", ["tiktok_blogger_id"])
    op.create_index("ix_blogger_tagging_results_status", "blogger_tagging_results", ["status"])


def downgrade() -> None:
    op.drop_table("blogger_tagging_results")
    op.drop_table("video_tagging_results")
