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


def upgrade() -> None:
    op.add_column('system_settings', sa.Column('use_seedance_api', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    op.drop_column('system_settings', 'use_seedance_api')
