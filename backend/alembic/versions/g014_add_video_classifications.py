"""add video classifications

Revision ID: g014_add_video_classifications
Revises: g013_add_promotion_code
Create Date: 2026-04-27 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "g014_add_video_classifications"
down_revision = "g013_add_promotion_code"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    existing_tables = set(inspector.get_table_names())
    if "video_classifications" not in existing_tables:
        op.create_table(
            "video_classifications",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("video_source_id", sa.Uuid(), nullable=False),
            sa.Column("owner_id", sa.Uuid(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("category_index", sa.Integer(), nullable=True),
            sa.Column("major_category", sa.String(length=20), nullable=True),
            sa.Column("raw_response", sa.Text(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("classified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["video_source_id"], ["video_sources.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("video_source_id", name="uq_video_classifications_video_source_id"),
        )
        op.create_index(
            "ix_video_classifications_video_source_id",
            "video_classifications",
            ["video_source_id"],
            unique=False,
        )
        op.create_index(
            "ix_video_classifications_owner_id",
            "video_classifications",
            ["owner_id"],
            unique=False,
        )
        op.create_index(
            "ix_video_classifications_status",
            "video_classifications",
            ["status"],
            unique=False,
        )

    account_columns = {column["name"] for column in inspector.get_columns("accounts")}
    if "classification_status" not in account_columns:
        op.add_column(
            "accounts",
            sa.Column(
                "classification_status",
                sa.String(length=20),
                nullable=False,
                server_default="idle",
            ),
        )
    if "classification_summary" not in account_columns:
        op.add_column("accounts", sa.Column("classification_summary", sa.JSON(), nullable=True))

    pipeline_columns = {column["name"] for column in inspector.get_columns("pipeline_settings")}
    if "video_classify_model" not in pipeline_columns:
        op.add_column(
            "pipeline_settings",
            sa.Column(
                "video_classify_model",
                sa.String(length=200),
                nullable=False,
                server_default="gemini-3.1-pro-preview",
            ),
        )
    if "video_classify_prompt" not in pipeline_columns:
        op.add_column(
            "pipeline_settings",
            sa.Column("video_classify_prompt", sa.Text(), nullable=False, server_default=""),
        )
    if "video_classify_temperature" not in pipeline_columns:
        op.add_column(
            "pipeline_settings",
            sa.Column(
                "video_classify_temperature",
                sa.Float(),
                nullable=False,
                server_default="0.0",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    pipeline_columns = {column["name"] for column in inspector.get_columns("pipeline_settings")}
    if "video_classify_temperature" in pipeline_columns:
        op.drop_column("pipeline_settings", "video_classify_temperature")
    if "video_classify_prompt" in pipeline_columns:
        op.drop_column("pipeline_settings", "video_classify_prompt")
    if "video_classify_model" in pipeline_columns:
        op.drop_column("pipeline_settings", "video_classify_model")

    account_columns = {column["name"] for column in inspector.get_columns("accounts")}
    if "classification_summary" in account_columns:
        op.drop_column("accounts", "classification_summary")
    if "classification_status" in account_columns:
        op.drop_column("accounts", "classification_status")

    existing_tables = set(inspector.get_table_names())
    if "video_classifications" in existing_tables:
        for index_name in (
            "ix_video_classifications_status",
            "ix_video_classifications_owner_id",
            "ix_video_classifications_video_source_id",
        ):
            try:
                op.drop_index(index_name, table_name="video_classifications")
            except Exception:
                pass
        op.drop_table("video_classifications")
