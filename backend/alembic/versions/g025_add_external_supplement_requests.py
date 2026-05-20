"""add external_supplement_requests

Revision ID: g025_add_ext_supplement
Revises: g024_add_sub_task_success_sample
Create Date: 2026-05-20

新表跟踪「补充模板」外包 vendor 的请求生命周期：
  request_id ↔ owner_id / mode / account_ids / filters / callback_secret / status
回调 (POST /api/v1/external/supplement-callback) 按 request_id 反查 + 鉴权。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "g025_add_ext_supplement"
down_revision = "g024_add_sub_task_success_sample"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "external_supplement_requests" in set(inspector.get_table_names()):
        return

    op.create_table(
        "external_supplement_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("mode", sa.String(length=20), nullable=False),  # exclusive | auto
        sa.Column("target_video_count", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("filters", sa.JSON(), nullable=True),
        sa.Column("account_ids", sa.JSON(), nullable=False),  # list[uuid str]
        sa.Column("callback_secret", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("vendor_request_payload", sa.JSON(), nullable=True),
        sa.Column("vendor_response", sa.JSON(), nullable=True),
        sa.Column("callbacks_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("videos_accepted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("videos_duplicated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("videos_rejected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", name="uq_external_supplement_requests_request_id"),
    )
    op.create_index(
        "ix_external_supplement_requests_owner_id",
        "external_supplement_requests",
        ["owner_id"],
    )
    op.create_index(
        "ix_external_supplement_requests_status",
        "external_supplement_requests",
        ["status"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "external_supplement_requests" not in set(inspector.get_table_names()):
        return
    for ix in ("ix_external_supplement_requests_status", "ix_external_supplement_requests_owner_id"):
        try:
            op.drop_index(ix, table_name="external_supplement_requests")
        except Exception:
            pass
    op.drop_table("external_supplement_requests")
