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


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _has_column('video_sub_tasks', 'manual_note'):
        op.add_column('video_sub_tasks', sa.Column('manual_note', sa.Text(), nullable=True))


def downgrade() -> None:
    if _has_column('video_sub_tasks', 'manual_note'):
        op.drop_column('video_sub_tasks', 'manual_note')
