"""drop ai account painting fields

Revision ID: g012_drop_ai_account_painting
Revises: g011_add_outfit_pipeline_fields
Create Date: 2026-04-24 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "g012_drop_ai_account_painting"
down_revision = "g011_add_outfit_pipeline_fields"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if _has_column("accounts", "painting_url"):
        op.drop_column("accounts", "painting_url")
    if _has_column("pipeline_settings", "ai_account_painting_prompt"):
        op.drop_column("pipeline_settings", "ai_account_painting_prompt")


def downgrade() -> None:
    if not _has_column("pipeline_settings", "ai_account_painting_prompt"):
        op.add_column("pipeline_settings", sa.Column("ai_account_painting_prompt", sa.Text(), nullable=False, server_default=""))
    if not _has_column("accounts", "painting_url"):
        op.add_column("accounts", sa.Column("painting_url", sa.Text(), nullable=True))
