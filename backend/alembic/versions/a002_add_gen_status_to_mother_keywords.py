"""add gen_status and gen_error to mother_keywords

Revision ID: a002_mk_gen_status
Revises: a001_topic_tables
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa

revision = "a002_mk_gen_status"
down_revision = "a001_topic_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    columns = [c["name"] for c in sa.inspect(conn).get_columns("mother_keywords")]
    if "gen_status" not in columns:
        op.add_column("mother_keywords", sa.Column("gen_status", sa.String(20), nullable=False, server_default="idle"))
    if "gen_error" not in columns:
        op.add_column("mother_keywords", sa.Column("gen_error", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("mother_keywords", "gen_error")
    op.drop_column("mother_keywords", "gen_status")
