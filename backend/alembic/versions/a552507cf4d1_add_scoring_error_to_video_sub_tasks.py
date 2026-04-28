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


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _has_column('video_sub_tasks', 'scoring_error'):
        op.add_column('video_sub_tasks', sa.Column('scoring_error', sa.Text(), nullable=True))


def downgrade() -> None:
    if _has_column('video_sub_tasks', 'scoring_error'):
        op.drop_column('video_sub_tasks', 'scoring_error')
