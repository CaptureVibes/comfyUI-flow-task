"""add hashtag search config to pipeline_settings

Revision ID: g003_add_hashtag_search_fields
Revises: g002_add_name_handle_fields
Create Date: 2026-04-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "g003_add_hashtag_search_fields"
down_revision = "g002_add_name_handle_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pipeline_settings", sa.Column(
        "hashtag_search_top_n", sa.Integer, nullable=False, server_default="100"
    ))
    op.add_column("pipeline_settings", sa.Column(
        "hashtag_filter_model", sa.String(200), nullable=False, server_default="gemini-3.1-pro-preview"
    ))
    op.add_column("pipeline_settings", sa.Column(
        "hashtag_filter_prompt", sa.Text, nullable=False, server_default=""
    ))


def downgrade() -> None:
    op.drop_column("pipeline_settings", "hashtag_search_top_n")
    op.drop_column("pipeline_settings", "hashtag_filter_model")
    op.drop_column("pipeline_settings", "hashtag_filter_prompt")
