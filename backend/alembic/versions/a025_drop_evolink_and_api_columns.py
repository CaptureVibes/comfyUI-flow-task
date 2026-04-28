"""Drop evolink_settings table and api columns from system_settings

API key now comes from .env (GOOGLE_API_KEY), no longer stored in DB.

Revision ID: a025
Revises: a024
"""
from alembic import op
import sqlalchemy as sa

revision = 'a025'
down_revision = 'a024'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop API key columns from system_settings (now in .env)
    op.execute(sa.text('ALTER TABLE system_settings DROP COLUMN IF EXISTS evolink_api_key'))
    op.execute(sa.text('ALTER TABLE system_settings DROP COLUMN IF EXISTS evolink_api_base_url'))

    # Drop the legacy evolink_settings table
    op.execute(sa.text('DROP TABLE IF EXISTS evolink_settings CASCADE'))


def downgrade() -> None:
    # Re-add API key columns to system_settings
    op.add_column('system_settings', sa.Column('evolink_api_base_url', sa.Text(), nullable=False, server_default='https://api.evolink.ai'))
    op.add_column('system_settings', sa.Column('evolink_api_key', sa.Text(), nullable=False, server_default=''))

    # Re-create evolink_settings table
    op.create_table(
        'evolink_settings',
        sa.Column('owner_id', sa.Uuid(), primary_key=True),
        sa.Column('api_key', sa.Text(), nullable=False, server_default=''),
        sa.Column('api_base_url', sa.Text(), nullable=False, server_default='https://api.evolink.ai'),
        sa.Column('understand_model', sa.String(200), nullable=False, server_default=''),
        sa.Column('understand_prompt', sa.Text(), nullable=False, server_default=''),
        sa.Column('understand_temperature', sa.Float(), nullable=False, server_default='0.3'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
