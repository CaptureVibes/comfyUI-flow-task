"""Add use_seedance_api column to system_settings

Revision ID: a026
Revises: a025
"""
from alembic import op
import sqlalchemy as sa

revision = 'a026'
down_revision = 'a025'
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _has_column('system_settings', 'use_seedance_api'):
        op.add_column('system_settings', sa.Column('use_seedance_api', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    if _has_column('system_settings', 'use_seedance_api'):
        op.drop_column('system_settings', 'use_seedance_api')
