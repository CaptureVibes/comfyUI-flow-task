"""add_scoring_error_to_video_sub_tasks

Revision ID: a552507cf4d1
Revises: 01d54967e900
Create Date: 2026-03-09 17:56:07.625979

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a552507cf4d1'
down_revision = '01d54967e900'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('video_sub_tasks', sa.Column('scoring_error', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('video_sub_tasks', 'scoring_error')
