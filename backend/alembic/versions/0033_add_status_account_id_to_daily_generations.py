"""add status, account_id, video_url, thumbnail_url, timestamps to daily_generations

Revision ID: 0033
Revises: 52dcecd3eb21
Create Date: 2026-03-05

"""
from alembic import op
import sqlalchemy as sa

revision = '0033'
down_revision = '52dcecd3eb21'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('daily_generations', sa.Column('account_id', sa.Uuid(as_uuid=True), nullable=True))
    op.add_column('daily_generations', sa.Column('status', sa.String(30), nullable=False, server_default='pending'))
    op.add_column('daily_generations', sa.Column('video_url', sa.Text(), nullable=True))
    op.add_column('daily_generations', sa.Column('thumbnail_url', sa.Text(), nullable=True))
    op.add_column('daily_generations', sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.add_column('daily_generations', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index('ix_daily_generations_account_id', 'daily_generations', ['account_id'])
    op.create_index('ix_daily_generations_status', 'daily_generations', ['status'])


def downgrade() -> None:
    op.drop_index('ix_daily_generations_status', table_name='daily_generations')
    op.drop_index('ix_daily_generations_account_id', table_name='daily_generations')
    op.drop_column('daily_generations', 'updated_at')
    op.drop_column('daily_generations', 'created_at')
    op.drop_column('daily_generations', 'thumbnail_url')
    op.drop_column('daily_generations', 'video_url')
    op.drop_column('daily_generations', 'status')
    op.drop_column('daily_generations', 'account_id')
