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


def upgrade() -> None:
    op.add_column('video_task_configs', sa.Column('top_percent', sa.Float(), nullable=False, server_default='30'))
    op.add_column('video_task_configs', sa.Column('discard_below', sa.Float(), nullable=False, server_default='40'))
    op.add_column('video_task_configs', sa.Column('select_percent', sa.Float(), nullable=False, server_default='50'))
    op.drop_column('video_task_configs', 'score_threshold_high')
    op.drop_column('video_task_configs', 'score_threshold_low')
    op.drop_column('video_task_configs', 'pool_ratio')


def downgrade() -> None:
    op.add_column('video_task_configs', sa.Column('score_threshold_high', sa.Float(), nullable=False, server_default='60'))
    op.add_column('video_task_configs', sa.Column('score_threshold_low', sa.Float(), nullable=False, server_default='20'))
    op.add_column('video_task_configs', sa.Column('pool_ratio', sa.Float(), nullable=False, server_default='0.75'))
    op.drop_column('video_task_configs', 'top_percent')
    op.drop_column('video_task_configs', 'discard_below')
    op.drop_column('video_task_configs', 'select_percent')
