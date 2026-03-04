from __future__ import annotations

"""add evolink_settings table

Revision ID: 0017_add_evolink_settings
Revises: 0016_add_accounts
Create Date: 2026-03-03 00:00:04.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0017_add_evolink_settings"
down_revision = "0016_add_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "evolink_settings" in existing_tables:
        return
    op.create_table(
        "evolink_settings",
        sa.Column("key", sa.String(32), primary_key=True),
        sa.Column("api_key", sa.Text(), nullable=False, server_default=""),
        sa.Column("model_name", sa.String(200), nullable=False, server_default="gemini-2.0-flash"),
        sa.Column("understand_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("extract_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("api_base_url", sa.Text(), nullable=False, server_default="https://api.evolink.ai"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "evolink_settings" in set(inspector.get_table_names()):
        op.drop_table("evolink_settings")
