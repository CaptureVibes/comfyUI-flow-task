"""add imagegen/splitting/face_removing to video_ai_process_status enum

Revision ID: 0037
Revises: 0036
Create Date: 2026-03-05
"""
from alembic import op

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE video_ai_process_status ADD VALUE IF NOT EXISTS 'imagegen'")
    op.execute("ALTER TYPE video_ai_process_status ADD VALUE IF NOT EXISTS 'splitting'")
    op.execute("ALTER TYPE video_ai_process_status ADD VALUE IF NOT EXISTS 'face_removing'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values directly
    pass
