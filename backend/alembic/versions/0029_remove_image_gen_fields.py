"""remove image_gen and extract fields from evolink_settings

Revision ID: 0029
Revises: 0028
Create Date: 2026-03-04
"""
from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 删除生图字段
    op.drop_column("evolink_settings", "image_gen_model")
    op.drop_column("evolink_settings", "image_gen_prompt_template")
    op.drop_column("evolink_settings", "image_gen_temperature")
    op.drop_column("evolink_settings", "image_gen_size")
    op.drop_column("evolink_settings", "image_gen_quality")
    op.drop_column("evolink_settings", "image_gen_output_format")
    op.drop_column("evolink_settings", "image_gen_json_schema")
    # 删除造型提取字段
    op.drop_column("evolink_settings", "extract_model")
    op.drop_column("evolink_settings", "extract_prompt")
    op.drop_column("evolink_settings", "extract_temperature")
    op.drop_column("evolink_settings", "extract_output_format")
    op.drop_column("evolink_settings", "extract_json_schema")


def downgrade() -> None:
    import sqlalchemy as sa
    op.add_column("evolink_settings", sa.Column("extract_json_schema", sa.Text(), nullable=False, server_default=""))
    op.add_column("evolink_settings", sa.Column("extract_output_format", sa.String(20), nullable=False, server_default="json"))
    op.add_column("evolink_settings", sa.Column("extract_temperature", sa.Float(), nullable=False, server_default="0.3"))
    op.add_column("evolink_settings", sa.Column("extract_prompt", sa.Text(), nullable=False, server_default=""))
    op.add_column("evolink_settings", sa.Column("extract_model", sa.String(200), nullable=False, server_default=""))
    op.add_column("evolink_settings", sa.Column("image_gen_json_schema", sa.Text(), nullable=False, server_default=""))
    op.add_column("evolink_settings", sa.Column("image_gen_output_format", sa.String(20), nullable=False, server_default="text"))
    op.add_column("evolink_settings", sa.Column("image_gen_quality", sa.String(10), nullable=False, server_default="2K"))
    op.add_column("evolink_settings", sa.Column("image_gen_size", sa.String(20), nullable=False, server_default="1:1"))
    op.add_column("evolink_settings", sa.Column("image_gen_temperature", sa.Float(), nullable=False, server_default="0.7"))
    op.add_column("evolink_settings", sa.Column("image_gen_prompt_template", sa.Text(), nullable=False, server_default=""))
    op.add_column("evolink_settings", sa.Column("image_gen_model", sa.String(200), nullable=False, server_default=""))
