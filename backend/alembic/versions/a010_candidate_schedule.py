"""add candidate schedule fields to pipeline_settings

Revision ID: a010_candidate_schedule
Revises: a009_candidate_filter_ai
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = "a010_candidate_schedule"
down_revision = "a009_candidate_filter_ai"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    existing_cols = {c["name"] for c in sa.inspect(conn).get_columns("pipeline_settings")}

    if "candidate_schedule_enabled" not in existing_cols:
        op.add_column("pipeline_settings", sa.Column("candidate_schedule_enabled", sa.Boolean(), nullable=False, server_default="false"))
    if "candidate_schedule_cron" not in existing_cols:
        op.add_column("pipeline_settings", sa.Column("candidate_schedule_cron", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("pipeline_settings", "candidate_schedule_cron")
    op.drop_column("pipeline_settings", "candidate_schedule_enabled")
