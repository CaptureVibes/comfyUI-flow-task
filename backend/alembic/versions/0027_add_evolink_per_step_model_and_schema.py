"""add per-step model, output format and json schema to evolink_settings

Revision ID: 0027
Revises: 0026
Create Date: 2026-03-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("evolink_settings", sa.Column("understand_model", sa.String(200), nullable=False, server_default=""))
    op.add_column("evolink_settings", sa.Column("understand_output_format", sa.String(20), nullable=False, server_default="text"))
    op.add_column("evolink_settings", sa.Column("understand_json_schema", sa.Text(), nullable=False, server_default=""))
    op.add_column("evolink_settings", sa.Column("extract_model", sa.String(200), nullable=False, server_default=""))
    op.add_column("evolink_settings", sa.Column("extract_json_schema", sa.Text(), nullable=False, server_default=""))
    op.add_column("evolink_settings", sa.Column("image_gen_output_format", sa.String(20), nullable=False, server_default="text"))
    op.add_column("evolink_settings", sa.Column("image_gen_json_schema", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("evolink_settings", "image_gen_json_schema")
    op.drop_column("evolink_settings", "image_gen_output_format")
    op.drop_column("evolink_settings", "extract_json_schema")
    op.drop_column("evolink_settings", "extract_model")
    op.drop_column("evolink_settings", "understand_json_schema")
    op.drop_column("evolink_settings", "understand_output_format")
    op.drop_column("evolink_settings", "understand_model")
