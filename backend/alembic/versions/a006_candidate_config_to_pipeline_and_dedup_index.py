"""move candidate config to pipeline_settings and add dedup index to candidate_videos

Revision ID: a006_candidate_config
Revises: a005_candidate_library
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = "a006_candidate_config"
down_revision = "a005_candidate_library"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. 给 candidate_videos 加 (keyword_id, blogger_unique_id, video_id) 联合唯一索引
    existing_indexes = {idx["name"] for idx in sa.inspect(conn).get_indexes("candidate_videos")}
    # 移除旧的双列唯一索引（如果存在）
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

    # 2. 把候选库配置字段加到 pipeline_settings（按用户独立配置）
    existing_cols = {c["name"] for c in sa.inspect(conn).get_columns("pipeline_settings")}
    if "candidate_max_bloggers" not in existing_cols:
        op.add_column("pipeline_settings", sa.Column("candidate_max_bloggers", sa.Integer(), nullable=False, server_default="20"))
    if "candidate_exclusive_threshold" not in existing_cols:
        op.add_column("pipeline_settings", sa.Column("candidate_exclusive_threshold", sa.Integer(), nullable=False, server_default="10"))
    if "candidate_max_videos_per_blogger" not in existing_cols:
        op.add_column("pipeline_settings", sa.Column("candidate_max_videos_per_blogger", sa.Integer(), nullable=False, server_default="100"))
    if "candidate_max_duration_seconds" not in existing_cols:
        op.add_column("pipeline_settings", sa.Column("candidate_max_duration_seconds", sa.Integer(), nullable=False, server_default="30"))
    if "candidate_retry_delay_seconds" not in existing_cols:
        op.add_column("pipeline_settings", sa.Column("candidate_retry_delay_seconds", sa.Integer(), nullable=False, server_default="5"))

    # 3. 从 system_settings 中删除候选库配置字段（已迁移到 pipeline_settings）
    sys_cols = {c["name"] for c in sa.inspect(conn).get_columns("system_settings")}
    for col in ["candidate_max_bloggers", "candidate_exclusive_threshold",
                "candidate_max_videos_per_blogger", "candidate_max_duration_seconds",
                "candidate_retry_delay_seconds"]:
        if col in sys_cols:
            op.drop_column("system_settings", col)


def downgrade() -> None:
    op.drop_index("uq_candidate_keyword_blogger_video", table_name="candidate_videos")
    for col in ["candidate_max_bloggers", "candidate_exclusive_threshold",
                "candidate_max_videos_per_blogger", "candidate_max_duration_seconds",
                "candidate_retry_delay_seconds"]:
        op.drop_column("pipeline_settings", col)
    # 恢复到 system_settings
    op.add_column("system_settings", sa.Column("candidate_max_bloggers", sa.Integer(), nullable=False, server_default="20"))
    op.add_column("system_settings", sa.Column("candidate_exclusive_threshold", sa.Integer(), nullable=False, server_default="10"))
    op.add_column("system_settings", sa.Column("candidate_max_videos_per_blogger", sa.Integer(), nullable=False, server_default="100"))
    op.add_column("system_settings", sa.Column("candidate_max_duration_seconds", sa.Integer(), nullable=False, server_default="30"))
    op.add_column("system_settings", sa.Column("candidate_retry_delay_seconds", sa.Integer(), nullable=False, server_default="5"))
