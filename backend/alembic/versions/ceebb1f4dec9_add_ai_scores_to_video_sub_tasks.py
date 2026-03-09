"""add_ai_scores_to_video_sub_tasks

Revision ID: ceebb1f4dec9
Revises: dbaa90e756dc
Create Date: 2026-03-09 17:21:02.593306

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ceebb1f4dec9'
down_revision = 'dbaa90e756dc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('video_sub_tasks', sa.Column('ai_score', sa.Integer(), nullable=True))
    op.add_column('video_sub_tasks', sa.Column('round1_score', sa.Integer(), nullable=True))
    op.add_column('video_sub_tasks', sa.Column('round2_score', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('video_sub_tasks', 'round2_score')
    op.drop_column('video_sub_tasks', 'round1_score')
    op.drop_column('video_sub_tasks', 'ai_score')
