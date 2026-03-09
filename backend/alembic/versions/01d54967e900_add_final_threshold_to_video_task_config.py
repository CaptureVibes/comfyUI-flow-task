"""add_final_threshold_to_video_task_config

Revision ID: 01d54967e900
Revises: ceebb1f4dec9
Create Date: 2026-03-09 17:42:09.474175

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '01d54967e900'
down_revision = 'ceebb1f4dec9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('video_task_configs', sa.Column('final_threshold', sa.Float(), nullable=False, server_default='65.0'))


def downgrade() -> None:
    op.drop_column('video_task_configs', 'final_threshold')
