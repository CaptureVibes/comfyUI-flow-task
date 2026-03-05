"""add splitting_api_url to pipeline_settings

Revision ID: 0038
Revises: 0037
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pipeline_settings",
        sa.Column("splitting_api_url", sa.String(500), nullable=False, server_default="http://34.21.127.95:8080"),
    )


def downgrade() -> None:
    op.drop_column("pipeline_settings", "splitting_api_url")
