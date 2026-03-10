"""add publish_error to video_sub_tasks

Revision ID: e99a762ac8ba
Revises: 0043
Create Date: 2026-03-10 17:31:54.864376

"""
from alembic import op
import sqlalchemy as sa

revision = 'e99a762ac8ba'
down_revision = '0043'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('video_sub_tasks', sa.Column('publish_error', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('video_sub_tasks', 'publish_error')
