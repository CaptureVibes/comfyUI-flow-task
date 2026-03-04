"""remove legacy fields from evolink_settings

Revision ID: 0030
Revises: 0029
Create Date: 2026-03-04
"""
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("evolink_settings", "model_name")
    op.drop_column("evolink_settings", "image_gen_api_base_url")
    op.drop_column("evolink_settings", "image_gen_api_key")


def downgrade() -> None:
    import sqlalchemy as sa
    op.add_column("evolink_settings", sa.Column("image_gen_api_key", sa.Text(), nullable=False, server_default=""))
    op.add_column("evolink_settings", sa.Column("image_gen_api_base_url", sa.Text(), nullable=False, server_default=""))
    op.add_column("evolink_settings", sa.Column("model_name", sa.String(200), nullable=False, server_default="gemini-2.0-flash"))
