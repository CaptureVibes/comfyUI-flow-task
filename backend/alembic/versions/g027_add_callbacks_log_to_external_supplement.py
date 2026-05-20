"""add callbacks_log column to external_supplement_requests

Revision ID: g027_add_callbacks_log
Revises: g026_add_rejected_videos
Create Date: 2026-05-20

每次 vendor 回调的 body 摘要追加到 callbacks_log，方便事后查 DB 看
本次 request 收到了几次回调、每次报了什么。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "g027_add_callbacks_log"
down_revision = "g026_add_rejected_videos"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns("external_supplement_requests")}
    if "callbacks_log" not in cols:
        op.add_column(
            "external_supplement_requests",
            sa.Column(
                "callbacks_log",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'::json"),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns("external_supplement_requests")}
    if "callbacks_log" in cols:
        op.drop_column("external_supplement_requests", "callbacks_log")
