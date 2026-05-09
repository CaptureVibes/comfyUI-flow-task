"""add tier evaluation settings to pipeline_settings

Revision ID: g021_add_tier_eval
Revises: g020_add_account_tier
Create Date: 2026-05-09

为账号分级判定规则增加 6 个可配参数（之前在 account_tier_scheduler.py 里硬编码）：
  tier_video_sample_count            最近 N 条视频
  tier_avg_play_threshold            均播阈值
  tier_activity_days                 最近 N 天
  tier_min_video_count               最近 N 天最少发视频数
  tier_daily_formal_growth_min_rate  正式号每日新增比例下限
  tier_daily_formal_growth_max_rate  正式号每日新增比例上限
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "g021_add_tier_eval"
down_revision = "g020_add_account_tier"
branch_labels = None
depends_on = None


_DEFAULTS: list[tuple[str, sa.types.TypeEngine, str | int | float]] = [
    ("tier_video_sample_count", sa.Integer(), 7),
    ("tier_avg_play_threshold", sa.Integer(), 700),
    ("tier_activity_days", sa.Integer(), 7),
    ("tier_min_video_count", sa.Integer(), 6),
    ("tier_daily_formal_growth_min_rate", sa.Float(), 0.0),
    ("tier_daily_formal_growth_max_rate", sa.Float(), 0.06),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {col["name"] for col in inspector.get_columns("pipeline_settings")}

    for name, sqltype, default in _DEFAULTS:
        if name in existing:
            continue
        op.add_column(
            "pipeline_settings",
            sa.Column(
                name,
                sqltype,
                nullable=False,
                server_default=str(default),
            ),
        )
        op.alter_column("pipeline_settings", name, server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {col["name"] for col in inspector.get_columns("pipeline_settings")}

    for name, _sqltype, _default in _DEFAULTS:
        if name in existing:
            op.drop_column("pipeline_settings", name)
