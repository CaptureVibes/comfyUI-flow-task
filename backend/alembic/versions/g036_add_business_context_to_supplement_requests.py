"""add business_context to external_supplement_requests

Revision ID: g036_add_business_context
Revises: g035_add_lookbook
Create Date: 2026-05-27

external_supplement_requests:
  - business_context (JSONB, nullable): 发起方写入的业务上下文，
    callback 时由对应业务域读取。不传给 vendor。
    示例（候选库）：{"source_domain": "candidate", "keyword_id": "...", "keyword_text": "..."}
    示例（AI博主）：{"source_domain": "ai_blogger"}
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "g036_add_business_context"
down_revision = "g035_add_lookbook"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "external_supplement_requests",
        sa.Column("business_context", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("external_supplement_requests", "business_context")
