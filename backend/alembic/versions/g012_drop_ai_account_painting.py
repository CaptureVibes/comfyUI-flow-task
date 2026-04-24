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


def upgrade() -> None:
    op.drop_column("accounts", "painting_url")
    op.drop_column("pipeline_settings", "ai_account_painting_prompt")


def downgrade() -> None:
    op.add_column("pipeline_settings", sa.Column("ai_account_painting_prompt", sa.Text(), nullable=False, server_default=""))
    op.add_column("accounts", sa.Column("painting_url", sa.Text(), nullable=True))
