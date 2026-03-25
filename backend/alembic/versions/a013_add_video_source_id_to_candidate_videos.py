"""add video_source_id FK to candidate_videos

Revision ID: a013_video_source_id
Revises: a012_shared_top_n
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = "a013_video_source_id"
down_revision = "a012_shared_top_n"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    existing_cols = {c["name"] for c in sa.inspect(conn).get_columns("candidate_videos")}

    if "video_source_id" not in existing_cols:
        op.add_column(
            "candidate_videos",
            sa.Column("video_source_id", sa.Uuid(as_uuid=True), sa.ForeignKey("video_sources.id", ondelete="SET NULL"), nullable=True),
        )
        op.create_index("ix_candidate_videos_video_source_id", "candidate_videos", ["video_source_id"])


def downgrade() -> None:
    conn = op.get_bind()
    existing_cols = {c["name"] for c in sa.inspect(conn).get_columns("candidate_videos")}

    if "video_source_id" in existing_cols:
        op.drop_index("ix_candidate_videos_video_source_id", table_name="candidate_videos")
        op.drop_column("candidate_videos", "video_source_id")
