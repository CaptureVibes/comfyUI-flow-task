"""change video_sources.video_title from varchar(500) to text

Revision ID: a016_video_title_text
Revises: a015_search_interval
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = "a016_video_title_text"
down_revision = "a015_search_interval"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "video_sources",
        "video_title",
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "video_sources",
        "video_title",
        type_=sa.String(500),
        existing_nullable=True,
    )
