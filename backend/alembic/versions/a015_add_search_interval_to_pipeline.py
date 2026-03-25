"""add candidate_search_interval_minutes to pipeline_settings

Revision ID: a015_search_interval
Revises: a014_import_attempts
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = "a015_search_interval"
down_revision = "a014_import_attempts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    existing_cols = {c["name"] for c in sa.inspect(conn).get_columns("pipeline_settings")}
    if "candidate_search_interval_minutes" not in existing_cols:
        op.add_column(
            "pipeline_settings",
            sa.Column("candidate_search_interval_minutes", sa.Integer(), server_default="0", nullable=False),
        )


def downgrade() -> None:
    conn = op.get_bind()
    existing_cols = {c["name"] for c in sa.inspect(conn).get_columns("pipeline_settings")}
    if "candidate_search_interval_minutes" in existing_cols:
        op.drop_column("pipeline_settings", "candidate_search_interval_minutes")
