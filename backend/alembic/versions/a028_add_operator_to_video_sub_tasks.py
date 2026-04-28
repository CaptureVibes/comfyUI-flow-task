"""Add operator field to video_sub_tasks.

Revision ID: a028
Revises: a027
Create Date: 2026-04-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'a028'
down_revision = 'a027'
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _has_index(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    if not _has_column('video_sub_tasks', 'operator'):
        op.add_column(
            'video_sub_tasks',
            sa.Column('operator', sa.String(100), nullable=True),
        )
    if not _has_index('video_sub_tasks', 'ix_video_sub_tasks_operator'):
        op.create_index('ix_video_sub_tasks_operator', 'video_sub_tasks', ['operator'])


def downgrade() -> None:
    if _has_index('video_sub_tasks', 'ix_video_sub_tasks_operator'):
        op.drop_index('ix_video_sub_tasks_operator', table_name='video_sub_tasks')
    if _has_column('video_sub_tasks', 'operator'):
        op.drop_column('video_sub_tasks', 'operator')
