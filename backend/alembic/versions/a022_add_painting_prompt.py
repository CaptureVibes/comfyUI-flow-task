"""add ai_account_painting_prompt to pipeline_settings

Revision ID: a022_add_painting_prompt
Revises: a021_add_account_type
Create Date: 2026-03-27
"""
import sqlalchemy as sa
from alembic import op

revision = "a022_add_painting_prompt"
down_revision = "a021_add_account_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pipeline_settings",
        sa.Column("ai_account_painting_prompt", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "accounts",
        sa.Column("painting_url", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pipeline_settings", "ai_account_painting_prompt")
    op.drop_column("accounts", "painting_url")
