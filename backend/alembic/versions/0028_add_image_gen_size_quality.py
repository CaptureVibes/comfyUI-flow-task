"""add image_gen_size and image_gen_quality to evolink_settings

Revision ID: 0028
Revises: 0027
Create Date: 2026-03-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("evolink_settings", sa.Column("image_gen_size", sa.String(20), nullable=False, server_default="1:1"))
    op.add_column("evolink_settings", sa.Column("image_gen_quality", sa.String(10), nullable=False, server_default="2K"))


def downgrade() -> None:
    op.drop_column("evolink_settings", "image_gen_quality")
    op.drop_column("evolink_settings", "image_gen_size")
