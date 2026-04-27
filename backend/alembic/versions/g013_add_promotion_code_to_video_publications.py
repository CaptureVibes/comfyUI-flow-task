"""add promotion code to video_publications

Revision ID: g013_add_promotion_code
Revises: g012_drop_ai_account_painting
Create Date: 2026-04-27 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "g013_add_promotion_code"
down_revision = "g012_drop_ai_account_painting"
branch_labels = None
depends_on = None


def _has_unique_promotion_code(inspector) -> bool:
    for index in inspector.get_indexes("video_publications"):
        if index.get("unique") and index.get("column_names") == ["promotion_code"]:
            return True
    for constraint in inspector.get_unique_constraints("video_publications"):
        if constraint.get("column_names") == ["promotion_code"]:
            return True
    return False


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    columns = {column["name"] for column in inspector.get_columns("video_publications")}
    if "promotion_code" not in columns:
        op.add_column("video_publications", sa.Column("promotion_code", sa.String(length=8), nullable=True))
    if "ext_products" not in columns:
        op.add_column("video_publications", sa.Column("ext_products", sa.JSON(), nullable=True))

    inspector = inspect(bind)
    if not _has_unique_promotion_code(inspector):
        op.create_index(
            "uq_video_publications_promotion_code",
            "video_publications",
            ["promotion_code"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    index_names = {index["name"] for index in inspector.get_indexes("video_publications")}
    if "uq_video_publications_promotion_code" in index_names:
        op.drop_index("uq_video_publications_promotion_code", table_name="video_publications")

    columns = {column["name"] for column in inspector.get_columns("video_publications")}
    if "ext_products" in columns:
        op.drop_column("video_publications", "ext_products")
    if "promotion_code" in columns:
        op.drop_column("video_publications", "promotion_code")
