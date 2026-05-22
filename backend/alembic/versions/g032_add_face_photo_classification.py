"""add face photo classification fields

Revision ID: g032_face_photo_classification
Revises: g031_fix_kol_status
Create Date: 2026-05-22
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "g032_face_photo_classification"
down_revision = "g031_fix_kol_status"
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


def _has_index(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return index_name in {idx["name"] for idx in inspector.get_indexes(table_name)}


def upgrade() -> None:
    _add_column_if_missing("face_photos", sa.Column("classification_status", sa.String(20), nullable=False, server_default="pending"))
    _add_column_if_missing("face_photos", sa.Column("classification_error", sa.Text(), nullable=True))
    _add_column_if_missing("face_photos", sa.Column("classification_model", sa.String(200), nullable=True))
    _add_column_if_missing("face_photos", sa.Column("classification_raw", sa.JSON(), nullable=True))
    _add_column_if_missing("face_photos", sa.Column("classified_at", sa.DateTime(timezone=True), nullable=True))
    _add_column_if_missing("face_photos", sa.Column("gender", sa.String(20), nullable=True))
    _add_column_if_missing("face_photos", sa.Column("ethnicity", sa.String(20), nullable=True))
    _add_column_if_missing("face_photos", sa.Column("age_estimate", sa.Integer(), nullable=True))
    _add_column_if_missing("face_photos", sa.Column("age_range", sa.String(20), nullable=True))
    _add_column_if_missing("face_photos", sa.Column("beauty_percentile", sa.Integer(), nullable=True))
    _add_column_if_missing("face_photos", sa.Column("beauty_level", sa.String(20), nullable=True))
    _add_column_if_missing("face_photos", sa.Column("memorability_percentile", sa.Integer(), nullable=True))
    _add_column_if_missing("face_photos", sa.Column("memorability_level", sa.String(20), nullable=True))
    _add_column_if_missing("face_photos", sa.Column("notes", sa.String(40), nullable=True))

    if not _has_index("face_photos", "ix_face_photos_remix_match"):
        op.create_index(
            "ix_face_photos_remix_match",
            "face_photos",
            ["owner_id", "gender", "ethnicity", "age_range", "beauty_level", "memorability_level"],
        )

    _add_column_if_missing("pipeline_settings", sa.Column("face_classify_model", sa.String(200), nullable=False, server_default="gemini-3-pro-preview"))
    _add_column_if_missing("pipeline_settings", sa.Column("face_classify_prompt", sa.Text(), nullable=False, server_default=""))
    _add_column_if_missing("pipeline_settings", sa.Column("face_classify_temperature", sa.Float(), nullable=False, server_default="0.5"))


def downgrade() -> None:
    if _has_index("face_photos", "ix_face_photos_remix_match"):
        op.drop_index("ix_face_photos_remix_match", table_name="face_photos")

    for column_name in [
        "face_classify_temperature",
        "face_classify_prompt",
        "face_classify_model",
    ]:
        _drop_column_if_exists("pipeline_settings", column_name)

    for column_name in [
        "notes",
        "memorability_level",
        "memorability_percentile",
        "beauty_level",
        "beauty_percentile",
        "age_range",
        "age_estimate",
        "ethnicity",
        "gender",
        "classified_at",
        "classification_raw",
        "classification_model",
        "classification_error",
        "classification_status",
    ]:
        _drop_column_if_exists("face_photos", column_name)
