"""replace candidate_max_publish_days with candidate_publish_after_date, fix default model

Revision ID: a011_publish_after_date
Revises: a010_candidate_schedule
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = "a011_publish_after_date"
down_revision = "a010_candidate_schedule"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    existing_cols = {c["name"] for c in sa.inspect(conn).get_columns("pipeline_settings")}

    if "candidate_publish_after_date" not in existing_cols:
        op.add_column("pipeline_settings", sa.Column("candidate_publish_after_date", sa.String(20), nullable=True))

    if "candidate_max_publish_days" in existing_cols:
        op.drop_column("pipeline_settings", "candidate_max_publish_days")

    # Fix default model
    op.execute("UPDATE pipeline_settings SET candidate_ai_review_model = 'gemini-3.1-pro-preview' WHERE candidate_ai_review_model = 'gemini-3.1-pro-preview'")


def downgrade() -> None:
    conn = op.get_bind()
    existing_cols = {c["name"] for c in sa.inspect(conn).get_columns("pipeline_settings")}

    if "candidate_max_publish_days" not in existing_cols:
        op.add_column("pipeline_settings", sa.Column("candidate_max_publish_days", sa.Integer(), nullable=False, server_default="0"))

    if "candidate_publish_after_date" in existing_cols:
        op.drop_column("pipeline_settings", "candidate_publish_after_date")
