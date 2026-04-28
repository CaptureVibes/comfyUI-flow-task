"""Replace pool config: score_threshold_high/low + pool_ratio → top_percent + discard_below + select_percent.

Revision ID: a029
Revises: a028
Create Date: 2026-04-02
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'a029'
down_revision = 'a028'
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if not _has_column(table_name, column.name):
        op.add_column(table_name, column)


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    if _has_column(table_name, column_name):
        op.drop_column(table_name, column_name)


def upgrade() -> None:
    _add_column_if_missing('video_task_configs', sa.Column('top_percent', sa.Float(), nullable=False, server_default='30'))
    _add_column_if_missing('video_task_configs', sa.Column('discard_below', sa.Float(), nullable=False, server_default='40'))
    _add_column_if_missing('video_task_configs', sa.Column('select_percent', sa.Float(), nullable=False, server_default='50'))
    _drop_column_if_exists('video_task_configs', 'score_threshold_high')
    _drop_column_if_exists('video_task_configs', 'score_threshold_low')
    _drop_column_if_exists('video_task_configs', 'pool_ratio')


def downgrade() -> None:
    _add_column_if_missing('video_task_configs', sa.Column('score_threshold_high', sa.Float(), nullable=False, server_default='60'))
    _add_column_if_missing('video_task_configs', sa.Column('score_threshold_low', sa.Float(), nullable=False, server_default='20'))
    _add_column_if_missing('video_task_configs', sa.Column('pool_ratio', sa.Float(), nullable=False, server_default='0.75'))
    _drop_column_if_exists('video_task_configs', 'top_percent')
    _drop_column_if_exists('video_task_configs', 'discard_below')
    _drop_column_if_exists('video_task_configs', 'select_percent')
