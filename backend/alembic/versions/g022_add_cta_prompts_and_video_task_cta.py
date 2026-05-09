"""add CTA prompt variants to pipeline_settings + cta flag to video_tasks

Revision ID: g022_add_cta
Revises: g021_add_tier_eval
Create Date: 2026-05-09

业务背景：流程配置里现有 9 个 prompt 视为「无CTA」（默认），新增同名 *_cta 列存放
「有CTA」版本。AI 模板的 enqueue 流程根据 cta 标志自动选用对应那一套。
video_tasks 增加 cta 列，由账号的 product_code_mode 决定（with_code → True）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "g022_add_cta"
down_revision = "g021_add_tier_eval"
branch_labels = None
depends_on = None


_CTA_PROMPT_COLUMNS = [
    "outfit_select_prompt_cta",
    "outfit_detail_prompt_cta",
    "intent_classify_prompt_cta",
    "understand_prompt_beauty_show_cta",
    "understand_prompt_knowledge_cta",
    "understand_prompt_persona_story_cta",
    "understand_prompt_trend_meme_cta",
    "product_imagegen_prompt_cta",
    "outfit_regen_prompt_cta",
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    # pipeline_settings: 9 个 *_cta 文本列，默认空字符串
    existing_pipeline = {col["name"] for col in inspector.get_columns("pipeline_settings")}
    for name in _CTA_PROMPT_COLUMNS:
        if name in existing_pipeline:
            continue
        op.add_column(
            "pipeline_settings",
            sa.Column(name, sa.Text(), nullable=False, server_default=""),
        )
        op.alter_column("pipeline_settings", name, server_default=None)

    # video_tasks.cta：默认 False
    existing_task = {col["name"] for col in inspector.get_columns("video_tasks")}
    if "cta" not in existing_task:
        op.add_column(
            "video_tasks",
            sa.Column("cta", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.alter_column("video_tasks", "cta", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    existing_task = {col["name"] for col in inspector.get_columns("video_tasks")}
    if "cta" in existing_task:
        op.drop_column("video_tasks", "cta")

    existing_pipeline = {col["name"] for col in inspector.get_columns("pipeline_settings")}
    for name in _CTA_PROMPT_COLUMNS:
        if name in existing_pipeline:
            op.drop_column("pipeline_settings", name)
