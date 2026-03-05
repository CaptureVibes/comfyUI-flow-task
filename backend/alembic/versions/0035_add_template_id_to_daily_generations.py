"""add template_id to daily_generations

Revision ID: 0035
Revises: 0034
Create Date: 2026-03-05

"""
from alembic import op
import sqlalchemy as sa

revision = '0035'
down_revision = '0034'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('daily_generations', sa.Column('template_id', sa.Uuid(as_uuid=True), nullable=True))
    op.create_index('ix_daily_generations_template_id', 'daily_generations', ['template_id'])


def downgrade() -> None:
    op.drop_index('ix_daily_generations_template_id', table_name='daily_generations')
    op.drop_column('daily_generations', 'template_id')
