"""add candidate_shared_top_n to pipeline_settings

Revision ID: a012_shared_top_n
Revises: a011_publish_after_date
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = "a012_shared_top_n"
down_revision = "a011_publish_after_date"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    existing_cols = {c["name"] for c in sa.inspect(conn).get_columns("pipeline_settings")}

    if "candidate_shared_top_n" not in existing_cols:
        op.add_column(
            "pipeline_settings",
            sa.Column("candidate_shared_top_n", sa.Integer(), nullable=False, server_default="50"),
        )


def downgrade() -> None:
    conn = op.get_bind()
    existing_cols = {c["name"] for c in sa.inspect(conn).get_columns("pipeline_settings")}

    if "candidate_shared_top_n" in existing_cols:
        op.drop_column("pipeline_settings", "candidate_shared_top_n")
