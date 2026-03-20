"""add_manual_score_to_video_sub_tasks

Revision ID: 70bea0df834f
Revises: 2cd2ebe0d0ff
Create Date: 2026-03-20 19:29:15.715318

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '70bea0df834f'
down_revision = '2cd2ebe0d0ff'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'video_sub_tasks',
        sa.Column('manual_score', sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('video_sub_tasks', 'manual_score')
