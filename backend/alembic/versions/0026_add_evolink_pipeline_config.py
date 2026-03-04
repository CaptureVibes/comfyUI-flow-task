"""add evolink pipeline config fields

Revision ID: 0026
Revises: 0025
Create Date: 2026-03-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0026"
down_revision = "0025_add_video_ai_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("evolink_settings", sa.Column("understand_temperature", sa.Float(), nullable=False, server_default="0.3"))
    op.add_column("evolink_settings", sa.Column("extract_temperature", sa.Float(), nullable=False, server_default="0.3"))
    op.add_column("evolink_settings", sa.Column("extract_output_format", sa.String(20), nullable=False, server_default="json"))
    op.add_column("evolink_settings", sa.Column("image_gen_api_base_url", sa.Text(), nullable=False, server_default=""))
    op.add_column("evolink_settings", sa.Column("image_gen_api_key", sa.Text(), nullable=False, server_default=""))
    op.add_column("evolink_settings", sa.Column("image_gen_model", sa.String(200), nullable=False, server_default=""))
    op.add_column("evolink_settings", sa.Column("image_gen_prompt_template", sa.Text(), nullable=False, server_default=""))
    op.add_column("evolink_settings", sa.Column("image_gen_temperature", sa.Float(), nullable=False, server_default="0.7"))


def downgrade() -> None:
    op.drop_column("evolink_settings", "image_gen_temperature")
    op.drop_column("evolink_settings", "image_gen_prompt_template")
    op.drop_column("evolink_settings", "image_gen_model")
    op.drop_column("evolink_settings", "image_gen_api_key")
    op.drop_column("evolink_settings", "image_gen_api_base_url")
    op.drop_column("evolink_settings", "extract_output_format")
    op.drop_column("evolink_settings", "extract_temperature")
    op.drop_column("evolink_settings", "understand_temperature")
