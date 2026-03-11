"""add queue_order to video_sub_tasks

Revision ID: 64b9a8ffd74b
Revises: 0048
Create Date: 2026-03-11 17:19:21.832138

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '64b9a8ffd74b'
down_revision = '0048'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('video_sub_tasks', sa.Column('queue_order', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('video_sub_tasks', 'queue_order')
