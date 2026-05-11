"""add formal_video_backfills

Revision ID: g023_add_formal_backfill
Revises: g022_add_cta
Create Date: 2026-05-11

临时表：把现有 prod 账号按 4/1→今天的曲线重新分配「转正日期」，用于做正式号
增长趋势图，并最终导出每个账号 D 及以后所有 openapi video_publication 的
open_api_task_id 列表。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "g023_add_formal_backfill"
down_revision = "g022_add_cta"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "formal_video_backfills" in existing_tables:
        return

    op.create_table(
        "formal_video_backfills",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("promotion_date", sa.Date(), nullable=False),
        sa.Column("trigger_publication_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["trigger_publication_id"], ["video_publications.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", name="uq_formal_video_backfills_account_id"),
    )
    op.create_index(
        "ix_formal_video_backfills_promotion_date",
        "formal_video_backfills",
        ["promotion_date"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "formal_video_backfills" not in existing_tables:
        return
    try:
        op.drop_index(
            "ix_formal_video_backfills_promotion_date",
            table_name="formal_video_backfills",
        )
    except Exception:
        pass
    op.drop_table("formal_video_backfills")
