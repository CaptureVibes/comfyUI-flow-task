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
    op.execute("""
        CREATE TABLE IF NOT EXISTS video_tagging_results (
            id UUID PRIMARY KEY,
            video_id UUID NOT NULL UNIQUE,
            gcs_url TEXT NOT NULL,
            description TEXT NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'pending',
            result_code INTEGER,
            result_message TEXT,
            error_code VARCHAR(50),
            error_message TEXT,
            video_description_unit JSONB,
            personal_tags JSONB,
            style_vector JSONB,
            style_signature JSONB,
            raw_outputs JSONB,
            source_type VARCHAR(50) NOT NULL DEFAULT 'direct',
            source_blogger_task_id UUID,
            source_tiktok_blogger_id UUID,
            worker_id VARCHAR(200),
            lock_until TIMESTAMPTZ,
            attempts INTEGER NOT NULL DEFAULT 0,
            next_retry_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            started_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_video_tagging_results_video_id ON video_tagging_results (video_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_video_tagging_results_status ON video_tagging_results (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_video_tagging_results_source_blogger ON video_tagging_results (source_tiktok_blogger_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS blogger_tagging_results (
            id UUID PRIMARY KEY,
            tiktok_blogger_id UUID NOT NULL UNIQUE,
            status VARCHAR(50) NOT NULL DEFAULT 'pending',
            result_code INTEGER,
            result_message TEXT,
            error_code VARCHAR(50),
            error_message TEXT,
            min_video_count INTEGER NOT NULL DEFAULT 15,
            available_video_count INTEGER NOT NULL DEFAULT 0,
            usable_video_count INTEGER NOT NULL DEFAULT 0,
            successful_video_count INTEGER NOT NULL DEFAULT 0,
            failed_video_count INTEGER NOT NULL DEFAULT 0,
            submitted_video_count INTEGER NOT NULL DEFAULT 0,
            selected_video_ids UUID[],
            video_task_ids UUID[],
            account_personal_tags JSONB,
            account_style_vector JSONB,
            account_style_signature JSONB,
            aggregated_social_identity JSONB,
            aggregated_occasion JSONB,
            raw_outputs JSONB,
            worker_id VARCHAR(200),
            lock_until TIMESTAMPTZ,
            attempts INTEGER NOT NULL DEFAULT 0,
            next_retry_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            started_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_blogger_tagging_results_blogger_id ON blogger_tagging_results (tiktok_blogger_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_blogger_tagging_results_status ON blogger_tagging_results (status)")


def downgrade() -> None:
    op.drop_table("blogger_tagging_results")
    op.drop_table("video_tagging_results")
