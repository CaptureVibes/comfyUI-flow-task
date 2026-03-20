"""add_manual_note_to_video_sub_tasks

Revision ID: f3c8e1a2b905
Revises: a552507cf4d1
Create Date: 2026-03-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f3c8e1a2b905'
down_revision = 'a552507cf4d1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('video_sub_tasks', sa.Column('manual_note', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('video_sub_tasks', 'manual_note')
