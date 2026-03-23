"""add topic, mother_keyword, keyword tables and keyword_gen config to pipeline_settings

Revision ID: a001_topic_tables
Revises: 70bea0df834f
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa

revision = "a001_topic_tables"
down_revision = "70bea0df834f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    existing_tables = sa.inspect(conn).get_table_names()

    if "topics" not in existing_tables:
        op.create_table(
            "topics",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )

    if "mother_keywords" not in existing_tables:
        op.create_table(
            "mother_keywords",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column("topic_id", sa.Uuid(as_uuid=True), sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False),
            sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )

    if "keywords" not in existing_tables:
        op.create_table(
            "keywords",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column("mother_keyword_id", sa.Uuid(as_uuid=True), sa.ForeignKey("mother_keywords.id", ondelete="CASCADE"), nullable=False),
            sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("keyword", sa.String(500), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    # Add keyword gen config columns to pipeline_settings
    columns = [c["name"] for c in sa.inspect(conn).get_columns("pipeline_settings")]
    if "keyword_gen_model" not in columns:
        op.add_column("pipeline_settings", sa.Column("keyword_gen_model", sa.String(200), nullable=False, server_default="gemini-3.1-pro-preview"))
    if "keyword_gen_prompt" not in columns:
        op.add_column("pipeline_settings", sa.Column("keyword_gen_prompt", sa.Text, nullable=False, server_default=""))
    if "keyword_gen_count" not in columns:
        op.add_column("pipeline_settings", sa.Column("keyword_gen_count", sa.Integer, nullable=False, server_default="50"))
    if "keyword_gen_temperature" not in columns:
        op.add_column("pipeline_settings", sa.Column("keyword_gen_temperature", sa.Float, nullable=False, server_default="0.7"))


def downgrade() -> None:
    op.drop_table("keywords")
    op.drop_table("mother_keywords")
    op.drop_table("topics")
    op.drop_column("pipeline_settings", "keyword_gen_model")
    op.drop_column("pipeline_settings", "keyword_gen_prompt")
    op.drop_column("pipeline_settings", "keyword_gen_count")
    op.drop_column("pipeline_settings", "keyword_gen_temperature")
