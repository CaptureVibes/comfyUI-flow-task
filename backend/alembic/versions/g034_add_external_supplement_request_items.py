"""add external supplement request items

Revision ID: g034_ext_supp_items
Revises: g033_add_local_gcs_video_url
Create Date: 2026-05-25
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "g034_ext_supp_items"
down_revision = "g033_add_local_gcs_video_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "external_supplement_request_items" in set(inspector.get_table_names()):
        return

    op.create_table(
        "external_supplement_request_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("blogger_handle", sa.String(length=200), nullable=True),
        sa.Column("target_video_count", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("completed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processing_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("final_received", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["external_supplement_requests.request_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "request_id",
            "account_id",
            name="uq_external_supplement_request_items_request_account",
        ),
    )
    op.create_index(
        "ix_external_supplement_request_items_request_id",
        "external_supplement_request_items",
        ["request_id"],
    )
    op.create_index(
        "ix_external_supplement_request_items_owner_id",
        "external_supplement_request_items",
        ["owner_id"],
    )
    op.create_index(
        "ix_external_supplement_request_items_account_id",
        "external_supplement_request_items",
        ["account_id"],
    )
    op.create_index(
        "ix_external_supplement_request_items_status",
        "external_supplement_request_items",
        ["status"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "external_supplement_request_items" not in set(inspector.get_table_names()):
        return
    for ix in (
        "ix_external_supplement_request_items_status",
        "ix_external_supplement_request_items_account_id",
        "ix_external_supplement_request_items_owner_id",
        "ix_external_supplement_request_items_request_id",
    ):
        try:
            op.drop_index(ix, table_name="external_supplement_request_items")
        except Exception:
            pass
    op.drop_table("external_supplement_request_items")
