from __future__ import annotations

"""add accounts table

Revision ID: 0016_add_accounts
Revises: 0015_add_video_ai_templates
Create Date: 2026-03-03 00:00:03.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0016_add_accounts"
down_revision = "0015_add_video_ai_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "accounts" in existing_tables:
        return
    op.create_table(
        "accounts",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("account_name", sa.String(200), nullable=False),
        sa.Column("style_description", sa.Text(), nullable=True),
        sa.Column("model_appearance", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("social_bindings", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "accounts" in set(inspector.get_table_names()):
        op.drop_table("accounts")
