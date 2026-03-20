"""expand_video_ai_template_title_to_text

Revision ID: 2cd2ebe0d0ff
Revises: 35ca5863b1f5
Create Date: 2026-03-20 18:04:58.183131

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2cd2ebe0d0ff'
down_revision = '35ca5863b1f5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        'video_ai_templates', 'title',
        existing_type=sa.VARCHAR(length=200),
        type_=sa.Text(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        'video_ai_templates', 'title',
        existing_type=sa.Text(),
        type_=sa.VARCHAR(length=200),
        existing_nullable=False,
    )
