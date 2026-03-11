"""Backfill video_ai_templates.tiktok_blogger_id from video_sources

Revision ID: 0048
Revises: 0047
Create Date: 2026-03-11 00:00:00.000000
"""

from alembic import op

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE video_ai_templates t
        SET tiktok_blogger_id = vs.tiktok_blogger_id
        FROM video_sources vs
        WHERE t.video_source_id = vs.id
          AND vs.tiktok_blogger_id IS NOT NULL
          AND t.tiktok_blogger_id IS NULL
        """
    )


def downgrade() -> None:
    # Backfill is safe to leave; clear if needed
    pass
