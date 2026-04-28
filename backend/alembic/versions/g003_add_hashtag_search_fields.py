"""add hashtag search config to pipeline_settings

Revision ID: g003_add_hashtag_search_fields
Revises: g002_add_name_handle_fields
Create Date: 2026-04-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "g003_add_hashtag_search_fields"
down_revision = "g002_add_name_handle_fields"
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
    _add_column_if_missing("pipeline_settings", sa.Column(
        "hashtag_search_top_n", sa.Integer, nullable=False, server_default="100"
    ))
    _add_column_if_missing("pipeline_settings", sa.Column(
        "hashtag_filter_model", sa.String(200), nullable=False, server_default="gemini-3.1-pro-preview"
    ))
    _add_column_if_missing("pipeline_settings", sa.Column(
        "hashtag_filter_prompt", sa.Text, nullable=False, server_default=""
    ))


def downgrade() -> None:
    _drop_column_if_exists("pipeline_settings", "hashtag_search_top_n")
    _drop_column_if_exists("pipeline_settings", "hashtag_filter_model")
    _drop_column_if_exists("pipeline_settings", "hashtag_filter_prompt")
