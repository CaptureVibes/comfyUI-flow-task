"""fix candidate dedup index: add video_id to unique constraint

Old index (keyword_id, blogger_unique_id) only allows 1 record per blogger per keyword,
but we store multiple videos per blogger. New index includes video_id.

Revision ID: a007_fix_candidate_dedup
Revises: a006_candidate_config
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = "a007_fix_candidate_dedup"
down_revision = "a006_candidate_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    existing_indexes = {idx["name"] for idx in sa.inspect(conn).get_indexes("candidate_videos")}

    # 删除旧的双列唯一索引
    if "uq_candidate_keyword_blogger" in existing_indexes:
        op.drop_index("uq_candidate_keyword_blogger", table_name="candidate_videos")

    # 创建新的三列唯一索引
    if "uq_candidate_keyword_blogger_video" not in existing_indexes:
        op.create_index(
            "uq_candidate_keyword_blogger_video",
            "candidate_videos",
            ["keyword_id", "blogger_unique_id", "video_id"],
            unique=True,
        )


def downgrade() -> None:
    conn = op.get_bind()
    existing_indexes = {idx["name"] for idx in sa.inspect(conn).get_indexes("candidate_videos")}

    if "uq_candidate_keyword_blogger_video" in existing_indexes:
        op.drop_index("uq_candidate_keyword_blogger_video", table_name="candidate_videos")

    if "uq_candidate_keyword_blogger" not in existing_indexes:
        op.create_index(
            "uq_candidate_keyword_blogger",
            "candidate_videos",
            ["keyword_id", "blogger_unique_id"],
            unique=True,
        )
