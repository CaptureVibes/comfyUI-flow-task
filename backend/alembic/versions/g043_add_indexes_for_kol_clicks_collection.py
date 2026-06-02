"""add indexes for kol_link_clicks collection queries

Revision ID: g043_kol_clicks_indexes
Revises: g042_kol_link_clicks
Create Date: 2026-06-02

加速每日 kol_link_clicks 收集任务的核心查询：
  WHERE status IN ('completed','partial')
    AND completed_at <= <cutoff>
    AND kol_link_clicks IS NULL
    JOIN accounts WHERE kol_user_id IS NOT NULL

- video_publications.completed_at              普通索引
- video_publications.kol_link_clicks IS NULL   部分索引（只索引未收集的行，随收集完成自动缩小）
- accounts.kol_user_id                         普通索引
"""
from __future__ import annotations

from alembic import op


revision = "g043_kol_clicks_indexes"
down_revision = "g042_kol_link_clicks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_video_publications_completed_at",
        "video_publications",
        ["completed_at"],
    )
    # 部分索引：只覆盖 kol_link_clicks IS NULL 的行，收集完后自动失效
    op.execute(
        "CREATE INDEX ix_video_publications_kol_link_clicks_null "
        "ON video_publications (id) "
        "WHERE kol_link_clicks IS NULL"
    )
    op.create_index(
        "ix_accounts_kol_user_id",
        "accounts",
        ["kol_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_accounts_kol_user_id", table_name="accounts")
    op.drop_index("ix_video_publications_kol_link_clicks_null", table_name="video_publications")
    op.drop_index("ix_video_publications_completed_at", table_name="video_publications")
