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


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if not _has_column(table_name, column.name):
        op.add_column(table_name, column)


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    if _has_column(table_name, column_name):
        op.drop_column(table_name, column_name)


def upgrade() -> None:
    # accounts 表新增 handle 和 signature
    _add_column_if_missing("accounts", sa.Column("account_handle", sa.String(200), nullable=True))
    _add_column_if_missing("accounts", sa.Column("account_signature", sa.Text, nullable=True))

    # pipeline_settings 表新增两个 prompt 字段
    _add_column_if_missing("pipeline_settings", sa.Column(
        "ai_account_exclusive_name_prompt", sa.Text, nullable=False, server_default=""
    ))
    _add_column_if_missing("pipeline_settings", sa.Column(
        "ai_account_shared_name_prompt", sa.Text, nullable=False, server_default=""
    ))


def downgrade() -> None:
    _drop_column_if_exists("accounts", "account_handle")
    _drop_column_if_exists("accounts", "account_signature")
    _drop_column_if_exists("pipeline_settings", "ai_account_exclusive_name_prompt")
    _drop_column_if_exists("pipeline_settings", "ai_account_shared_name_prompt")
