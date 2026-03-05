"""replace video_url/thumbnail_url with result_videos JSON + selected_video_url

Revision ID: 0034
Revises: 0033
Create Date: 2026-03-05

"""
from alembic import op
import sqlalchemy as sa

revision = '0034'
down_revision = '0033'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('daily_generations', 'video_url')
    op.drop_column('daily_generations', 'thumbnail_url')
    op.add_column('daily_generations', sa.Column('result_videos', sa.JSON(), nullable=True))
    op.add_column('daily_generations', sa.Column('selected_video_url', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('daily_generations', 'selected_video_url')
    op.drop_column('daily_generations', 'result_videos')
    op.add_column('daily_generations', sa.Column('thumbnail_url', sa.Text(), nullable=True))
    op.add_column('daily_generations', sa.Column('video_url', sa.Text(), nullable=True))
