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


def upgrade() -> None:
    op.add_column(
        'video_sub_tasks',
        sa.Column('operator', sa.String(100), nullable=True),
    )
    op.create_index('ix_video_sub_tasks_operator', 'video_sub_tasks', ['operator'])


def downgrade() -> None:
    op.drop_index('ix_video_sub_tasks_operator', table_name='video_sub_tasks')
    op.drop_column('video_sub_tasks', 'operator')
