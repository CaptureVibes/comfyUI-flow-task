"""add candidate filter (min_play_count, max_publish_days) and AI review config

Revision ID: a009_candidate_filter_ai
Revises: a008_cdn_cover_url
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = "a009_candidate_filter_ai"
down_revision = "a008_cdn_cover_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    existing_cols = {c["name"] for c in sa.inspect(conn).get_columns("pipeline_settings")}

    if "candidate_min_play_count" not in existing_cols:
        op.add_column("pipeline_settings", sa.Column("candidate_min_play_count", sa.Integer(), nullable=False, server_default="0"))
    if "candidate_max_publish_days" not in existing_cols:
        op.add_column("pipeline_settings", sa.Column("candidate_max_publish_days", sa.Integer(), nullable=False, server_default="0"))
    if "candidate_ai_review_enabled" not in existing_cols:
        op.add_column("pipeline_settings", sa.Column("candidate_ai_review_enabled", sa.Boolean(), nullable=False, server_default="false"))
    if "candidate_ai_review_model" not in existing_cols:
        op.add_column("pipeline_settings", sa.Column("candidate_ai_review_model", sa.String(200), nullable=False, server_default="gemini-2.0-flash"))
    if "candidate_ai_review_prompt" not in existing_cols:
        op.add_column("pipeline_settings", sa.Column("candidate_ai_review_prompt", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    for col in ["candidate_min_play_count", "candidate_max_publish_days",
                "candidate_ai_review_enabled", "candidate_ai_review_model", "candidate_ai_review_prompt"]:
        op.drop_column("pipeline_settings", col)
