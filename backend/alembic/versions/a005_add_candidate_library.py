"""add candidate_videos table and candidate search config to system_settings

Revision ID: a005_candidate_library
Revises: a004_elsa_score
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = "a005_candidate_library"
down_revision = "a004_elsa_score"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    existing_tables = sa.inspect(conn).get_table_names()

    # 创建候选视频表
    if "candidate_videos" not in existing_tables:
        op.create_table(
            "candidate_videos",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=True, index=True),
            sa.Column("keyword_id", sa.Uuid(as_uuid=True), nullable=True, index=True),
            sa.Column("keyword_text", sa.String(500), nullable=False),
            sa.Column("template_type", sa.String(20), nullable=False),  # shared | exclusive
            # 博主信息
            sa.Column("blogger_unique_id", sa.String(200), nullable=False),
            sa.Column("blogger_nickname", sa.String(200), nullable=True),
            sa.Column("blogger_follower_count", sa.BigInteger(), nullable=True),
            # 视频信息
            sa.Column("video_id", sa.String(100), nullable=False),
            sa.Column("video_url", sa.Text, nullable=True),
            sa.Column("video_title", sa.Text, nullable=True),
            sa.Column("duration", sa.Integer(), nullable=True),
            sa.Column("cover_url", sa.Text, nullable=True),
            sa.Column("play_count", sa.BigInteger(), nullable=True),
            sa.Column("like_count", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    # 在 system_settings 表添加候选库搜索参数
    existing_cols = {c["name"] for c in sa.inspect(conn).get_columns("system_settings")}

    if "candidate_max_bloggers" not in existing_cols:
        op.add_column("system_settings", sa.Column("candidate_max_bloggers", sa.Integer(), nullable=False, server_default="20"))
    if "candidate_exclusive_threshold" not in existing_cols:
        op.add_column("system_settings", sa.Column("candidate_exclusive_threshold", sa.Integer(), nullable=False, server_default="10"))
    if "candidate_max_videos_per_blogger" not in existing_cols:
        op.add_column("system_settings", sa.Column("candidate_max_videos_per_blogger", sa.Integer(), nullable=False, server_default="100"))
    if "candidate_max_duration_seconds" not in existing_cols:
        op.add_column("system_settings", sa.Column("candidate_max_duration_seconds", sa.Integer(), nullable=False, server_default="30"))
    if "candidate_retry_delay_seconds" not in existing_cols:
        op.add_column("system_settings", sa.Column("candidate_retry_delay_seconds", sa.Integer(), nullable=False, server_default="5"))


def downgrade() -> None:
    op.drop_table("candidate_videos")
    op.drop_column("system_settings", "candidate_max_bloggers")
    op.drop_column("system_settings", "candidate_exclusive_threshold")
    op.drop_column("system_settings", "candidate_max_videos_per_blogger")
    op.drop_column("system_settings", "candidate_max_duration_seconds")
    op.drop_column("system_settings", "candidate_retry_delay_seconds")
