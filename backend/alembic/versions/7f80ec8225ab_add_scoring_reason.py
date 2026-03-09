"""add scoring_reason

Revision ID: 7f80ec8225ab
Revises: a552507cf4d1
Create Date: 2026-03-09 19:03:36.525946

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '7f80ec8225ab'
down_revision = 'a552507cf4d1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('video_sub_tasks', sa.Column('scoring_reason', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('video_sub_tasks', 'scoring_reason')

