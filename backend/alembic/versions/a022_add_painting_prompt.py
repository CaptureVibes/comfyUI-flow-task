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
    _add_column_if_missing(
        "pipeline_settings",
        sa.Column("ai_account_painting_prompt", sa.Text(), nullable=False, server_default=""),
    )
    _add_column_if_missing(
        "accounts",
        sa.Column("painting_url", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    _drop_column_if_exists("pipeline_settings", "ai_account_painting_prompt")
    _drop_column_if_exists("accounts", "painting_url")
