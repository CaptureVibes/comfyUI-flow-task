"""add face_select fields to pipeline_settings

Revision ID: a019_face_select_pipeline
Revises: a018_face_photos
Create Date: 2026-03-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "a019_face_select_pipeline"
down_revision = "a018_face_photos"
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
        sa.Column("face_select_model", sa.String(200), nullable=False, server_default="gemini-3.1-pro-preview"),
    )
    _add_column_if_missing(
        "pipeline_settings",
        sa.Column("face_select_prompt", sa.Text, nullable=False, server_default=""),
    )


def downgrade() -> None:
    _drop_column_if_exists("pipeline_settings", "face_select_prompt")
    _drop_column_if_exists("pipeline_settings", "face_select_model")
