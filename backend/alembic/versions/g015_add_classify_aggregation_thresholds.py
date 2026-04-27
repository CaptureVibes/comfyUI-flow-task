"""add classify aggregation thresholds to pipeline_settings

Revision ID: g015_classify_thresholds
Revises: g014_add_video_classifications
Create Date: 2026-04-27 00:30:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "g015_classify_thresholds"
down_revision = "g014_add_video_classifications"
branch_labels = None
depends_on = None


_COLUMNS = (
    ("classify_min_sample", sa.Integer(), "3"),
    ("classify_single_top1_threshold", sa.Float(), "0.5"),
    ("classify_single_diff_threshold", sa.Float(), "0.15"),
    ("classify_dual_top1_lower", sa.Float(), "0.35"),
    ("classify_dual_top1_upper", sa.Float(), "0.5"),
    ("classify_dual_top2_threshold", sa.Float(), "0.2"),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {column["name"] for column in inspector.get_columns("pipeline_settings")}
    for name, col_type, default in _COLUMNS:
        if name not in existing:
            op.add_column(
                "pipeline_settings",
                sa.Column(name, col_type, nullable=False, server_default=default),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {column["name"] for column in inspector.get_columns("pipeline_settings")}
    for name, _col_type, _default in reversed(_COLUMNS):
        if name in existing:
            op.drop_column("pipeline_settings", name)
