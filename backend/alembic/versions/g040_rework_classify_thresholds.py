"""rework classify thresholds: per-major single thresholds + dual combined

Revision ID: g040_classify_thresh
Revises: g039_category_key
Create Date: 2026-06-01

pipeline_settings:
  删除旧字段：
    classify_single_top1_threshold, classify_single_diff_threshold,
    classify_dual_top1_lower, classify_dual_top1_upper, classify_dual_top2_threshold
  新增字段（每个大类独立单核心阈值 + 双核心合计阈值）：
    classify_beauty_threshold   float default 0.75
    classify_method_threshold   float default 0.60
    classify_shopping_threshold float default 0.55
    classify_lifestyle_threshold float default 0.55
    classify_drama_threshold    float default 0.65
    classify_dual_combined_threshold float default 0.80
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "g040_classify_thresh"
down_revision = "g039_category_key"
branch_labels = None
depends_on = None

_OLD_COLS = [
    "classify_single_top1_threshold",
    "classify_single_diff_threshold",
    "classify_dual_top1_lower",
    "classify_dual_top1_upper",
    "classify_dual_top2_threshold",
]

_NEW_COLS = [
    ("classify_beauty_threshold",    0.75),
    ("classify_method_threshold",    0.60),
    ("classify_shopping_threshold",  0.55),
    ("classify_lifestyle_threshold", 0.55),
    ("classify_drama_threshold",     0.65),
    ("classify_dual_combined_threshold", 0.80),
]


def upgrade() -> None:
    for col in _OLD_COLS:
        op.drop_column("pipeline_settings", col)
    for col_name, default in _NEW_COLS:
        op.add_column(
            "pipeline_settings",
            sa.Column(col_name, sa.Float, nullable=False, server_default=str(default)),
        )


def downgrade() -> None:
    for col_name, _ in _NEW_COLS:
        op.drop_column("pipeline_settings", col_name)
    for col in _OLD_COLS:
        op.add_column(
            "pipeline_settings",
            sa.Column(col, sa.Float, nullable=False, server_default="0.5"),
        )
