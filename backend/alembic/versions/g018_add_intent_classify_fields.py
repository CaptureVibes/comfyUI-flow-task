"""add intent_classify + branch understand prompts to pipeline_settings

Revision ID: g018_add_intent_classify
Revises: g017_add_product_code_mode
Create Date: 2026-04-29
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "g018_add_intent_classify"
down_revision = "g017_add_product_code_mode"
branch_labels = None
depends_on = None


_NEW_TEXT_COLUMNS = (
    "understand_prompt_beauty_show",
    "understand_prompt_knowledge",
    "understand_prompt_persona_story",
    "understand_prompt_trend_meme",
    "intent_classify_prompt",
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {col["name"] for col in inspector.get_columns("pipeline_settings")}

    for name in _NEW_TEXT_COLUMNS:
        if name not in existing:
            op.add_column(
                "pipeline_settings",
                sa.Column(name, sa.Text(), nullable=False, server_default=""),
            )
            op.alter_column("pipeline_settings", name, server_default=None)

    if "intent_classify_model" not in existing:
        op.add_column(
            "pipeline_settings",
            sa.Column(
                "intent_classify_model",
                sa.String(length=200),
                nullable=False,
                server_default="gemini-3.1-pro-preview",
            ),
        )
        op.alter_column("pipeline_settings", "intent_classify_model", server_default=None)

    if "intent_classify_temperature" not in existing:
        op.add_column(
            "pipeline_settings",
            sa.Column(
                "intent_classify_temperature",
                sa.Float(),
                nullable=False,
                server_default="0.3",
            ),
        )
        op.alter_column("pipeline_settings", "intent_classify_temperature", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {col["name"] for col in inspector.get_columns("pipeline_settings")}

    for name in (
        "intent_classify_temperature",
        "intent_classify_model",
        *_NEW_TEXT_COLUMNS,
    ):
        if name in existing:
            op.drop_column("pipeline_settings", name)
