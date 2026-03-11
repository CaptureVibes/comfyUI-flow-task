"""Refactor video_source_tags, add template fields, add account_tiktok_bloggers

Revision ID: 0047
Revises: 0046
Create Date: 2026-03-11 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # 1. 重建 video_source_tags 表（旧版为复合主键，新版改为有 id/owner_id 的普通表）
    if "video_source_tags" in existing_tables:
        op.drop_table("video_source_tags")

    op.create_table(
        "video_source_tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "video_source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("video_sources.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "video_ai_template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("video_ai_templates.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "tag_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tags.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_video_source_tags_owner_id", "video_source_tags", ["owner_id"])
    op.create_index("ix_video_source_tags_video_source_id", "video_source_tags", ["video_source_id"])
    op.create_index("ix_video_source_tags_video_ai_template_id", "video_source_tags", ["video_ai_template_id"])
    op.create_index("ix_video_source_tags_tag_id", "video_source_tags", ["tag_id"])
    # 部分唯一约束：同一 (video_source_id, tag_id) 或 (video_ai_template_id, tag_id) 不重复
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_video_source_tags_vs_tag "
        "ON video_source_tags (video_source_id, tag_id) "
        "WHERE video_source_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_video_source_tags_tpl_tag "
        "ON video_source_tags (video_ai_template_id, tag_id) "
        "WHERE video_ai_template_id IS NOT NULL"
    )

    # 2. video_ai_templates 表新增 repeatable 和 tiktok_blogger_id
    tpl_cols = {c["name"] for c in inspector.get_columns("video_ai_templates")}

    if "repeatable" not in tpl_cols:
        op.add_column(
            "video_ai_templates",
            sa.Column("repeatable", sa.Boolean(), nullable=False, server_default="false"),
        )

    if "tiktok_blogger_id" not in tpl_cols:
        op.add_column(
            "video_ai_templates",
            sa.Column(
                "tiktok_blogger_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("tiktok_bloggers.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        op.create_index("ix_video_ai_templates_tiktok_blogger_id", "video_ai_templates", ["tiktok_blogger_id"])

    # 3. 创建 account_tiktok_bloggers 关联表
    if "account_tiktok_bloggers" not in existing_tables:
        op.create_table(
            "account_tiktok_bloggers",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "account_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("accounts.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "tiktok_blogger_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("tiktok_bloggers.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_account_tiktok_bloggers_account_id", "account_tiktok_bloggers", ["account_id"])
        op.create_index(
            "ix_account_tiktok_bloggers_tiktok_blogger_id", "account_tiktok_bloggers", ["tiktok_blogger_id"]
        )
        op.create_unique_constraint(
            "uq_account_tiktok_bloggers",
            "account_tiktok_bloggers",
            ["account_id", "tiktok_blogger_id"],
        )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS account_tiktok_bloggers")
    op.execute("DROP INDEX IF EXISTS ix_video_ai_templates_tiktok_blogger_id")
    op.execute("ALTER TABLE video_ai_templates DROP COLUMN IF EXISTS tiktok_blogger_id")
    op.execute("ALTER TABLE video_ai_templates DROP COLUMN IF EXISTS repeatable")
    op.execute("DROP TABLE IF EXISTS video_source_tags")
    # 还原旧版 video_source_tags（复合主键）
    op.create_table(
        "video_source_tags",
        sa.Column(
            "video_source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("video_sources.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tag_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tags.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
