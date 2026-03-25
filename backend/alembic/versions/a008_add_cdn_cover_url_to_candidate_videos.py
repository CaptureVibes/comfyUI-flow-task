"""add cdn_cover_url to candidate_videos

Revision ID: a008_cdn_cover_url
Revises: a007_fix_candidate_dedup
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = "a008_cdn_cover_url"
down_revision = "a007_fix_candidate_dedup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    existing_cols = {c["name"] for c in sa.inspect(conn).get_columns("candidate_videos")}
    if "cdn_cover_url" not in existing_cols:
        op.add_column("candidate_videos", sa.Column("cdn_cover_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("candidate_videos", "cdn_cover_url")
