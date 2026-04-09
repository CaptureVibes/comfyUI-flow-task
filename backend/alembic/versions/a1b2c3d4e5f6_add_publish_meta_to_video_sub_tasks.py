"""add_publish_meta_to_video_sub_tasks

Revision ID: a1b2c3d4e5f6
Revises: f3c8e1a2b905
Create Date: 2026-04-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '0060'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'video_sub_tasks',
        sa.Column('publish_meta', JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column('video_sub_tasks', 'publish_meta')
