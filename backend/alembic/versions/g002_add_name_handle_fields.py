"""add account_handle/signature and exclusive/shared name prompts

Revision ID: g002_add_name_handle_fields
Revises: g001_rename_traffic_to_shared
Create Date: 2026-04-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "g002_add_name_handle_fields"
down_revision = "g001_rename_traffic_to_shared"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # accounts 表新增 handle 和 signature
    op.add_column("accounts", sa.Column("account_handle", sa.String(200), nullable=True))
    op.add_column("accounts", sa.Column("account_signature", sa.Text, nullable=True))

    # pipeline_settings 表新增两个 prompt 字段
    op.add_column("pipeline_settings", sa.Column(
        "ai_account_exclusive_name_prompt", sa.Text, nullable=False, server_default=""
    ))
    op.add_column("pipeline_settings", sa.Column(
        "ai_account_shared_name_prompt", sa.Text, nullable=False, server_default=""
    ))


def downgrade() -> None:
    op.drop_column("accounts", "account_handle")
    op.drop_column("accounts", "account_signature")
    op.drop_column("pipeline_settings", "ai_account_exclusive_name_prompt")
    op.drop_column("pipeline_settings", "ai_account_shared_name_prompt")
