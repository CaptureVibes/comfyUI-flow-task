"""add category_key to video_classifications

Revision ID: g039_category_key
Revises: g038_cv_hidden
Create Date: 2026-06-01

video_classifications:
  - category_key (String(60), nullable): 分类 slug，替代 category_index 整数下标。
    category_index 列保留但不再写入（废弃），等后续确认无历史依赖后可再迁移删除。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "g039_category_key"
down_revision = "g038_cv_hidden"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "video_classifications",
        sa.Column("category_key", sa.String(60), nullable=True),
    )
    op.create_index(
        "ix_video_classifications_category_key",
        "video_classifications",
        ["category_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_video_classifications_category_key", table_name="video_classifications")
    op.drop_column("video_classifications", "category_key")
