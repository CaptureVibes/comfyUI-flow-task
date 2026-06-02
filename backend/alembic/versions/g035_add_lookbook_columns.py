"""add lookbook stage columns

Revision ID: g035_add_lookbook
Revises: g034_ext_supp_items
Create Date: 2026-05-26

新增「阶段 2.5：8 拼图生成与拆分」+ 多次重洗机制：

video_ai_templates:
  - lookbooks (JSONB): 每个 outfit_shot 对应一个 lookbook 结构
  - remix_history (JSONB): 重洗历史数组
  - remix_count (INT): 重洗计数

pipeline_settings:
  - lookbook_analysis_model / prompt / temperature
  - lookbook_imagegen_model / prompt / size / quality
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision = "g035_add_lookbook"
down_revision = "g034_ext_supp_items"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def _add_if_missing(table_name: str, column: sa.Column) -> None:
    if not _has_column(table_name, column.name):
        op.add_column(table_name, column)


def _drop_if_exists(table_name: str, column_name: str) -> None:
    if _has_column(table_name, column_name):
        op.drop_column(table_name, column_name)


def upgrade() -> None:
    # 给 VideoAIProcessStatus 枚举类型加新值（idempotent，IF NOT EXISTS）
    op.execute("ALTER TYPE video_ai_process_status ADD VALUE IF NOT EXISTS 'lookbook_gen'")
    op.execute("ALTER TYPE video_ai_process_status ADD VALUE IF NOT EXISTS 'remixing'")

    # video_ai_templates
    _add_if_missing("video_ai_templates", sa.Column("lookbooks", JSONB, nullable=True))
    _add_if_missing("video_ai_templates", sa.Column("remix_history", JSONB, nullable=True))
    _add_if_missing(
        "video_ai_templates",
        sa.Column("remix_count", sa.Integer(), nullable=False, server_default="0"),
    )

    # pipeline_settings - lookbook 分析（Gemini 文本读图产 prompt）
    _add_if_missing(
        "pipeline_settings",
        sa.Column(
            "lookbook_analysis_model",
            sa.String(200),
            nullable=False,
            server_default="gemini-3-pro-preview",
        ),
    )
    _add_if_missing(
        "pipeline_settings",
        sa.Column("lookbook_analysis_prompt", sa.Text(), nullable=False, server_default=""),
    )
    _add_if_missing(
        "pipeline_settings",
        sa.Column(
            "lookbook_analysis_temperature",
            sa.Float(),
            nullable=False,
            server_default="0.3",
        ),
    )

    # pipeline_settings - lookbook 图像生成（4×2 八拼图）
    _add_if_missing(
        "pipeline_settings",
        sa.Column(
            "lookbook_imagegen_model",
            sa.String(200),
            nullable=False,
            server_default="gemini-3.1-flash-image-preview",
        ),
    )
    _add_if_missing(
        "pipeline_settings",
        sa.Column("lookbook_imagegen_prompt", sa.Text(), nullable=False, server_default=""),
    )
    _add_if_missing(
        "pipeline_settings",
        sa.Column(
            "lookbook_imagegen_size", sa.String(20), nullable=False, server_default="4:3"
        ),
    )
    _add_if_missing(
        "pipeline_settings",
        sa.Column(
            "lookbook_imagegen_quality", sa.String(20), nullable=False, server_default="2K"
        ),
    )
    # 修正之前 migration 跑过、defaults 写错的存量行
    # - size/quality 语义颠倒（size 原是 "2K"，quality 原是 "high"）
    # - imagegen_model 原为不存在的 "gemini-3-pro-image-preview"
    op.execute(
        """
        UPDATE pipeline_settings
        SET lookbook_imagegen_size = '4:3'
        WHERE lookbook_imagegen_size IN ('2K', '1K', 'high', 'standard') OR lookbook_imagegen_size IS NULL
        """
    )
    op.execute(
        """
        UPDATE pipeline_settings
        SET lookbook_imagegen_quality = '2K'
        WHERE lookbook_imagegen_quality NOT IN ('1K', '2K') OR lookbook_imagegen_quality IS NULL
        """
    )
    op.execute(
        """
        UPDATE pipeline_settings
        SET lookbook_imagegen_model = 'gemini-3.1-flash-image-preview'
        WHERE lookbook_imagegen_model = 'gemini-3-pro-image-preview'
        """
    )


def downgrade() -> None:
    for col in (
        "lookbook_imagegen_quality",
        "lookbook_imagegen_size",
        "lookbook_imagegen_prompt",
        "lookbook_imagegen_model",
        "lookbook_analysis_temperature",
        "lookbook_analysis_prompt",
        "lookbook_analysis_model",
    ):
        _drop_if_exists("pipeline_settings", col)
    for col in ("remix_count", "remix_history", "lookbooks"):
        _drop_if_exists("video_ai_templates", col)
