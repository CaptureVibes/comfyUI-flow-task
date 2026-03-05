"""add imagegen fields to pipeline_settings

Revision ID: 0036
Revises: 0035
Create Date: 2026-03-05
"""
import sqlalchemy as sa
from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pipeline_settings", sa.Column("imagegen_model", sa.String(200), nullable=False, server_default="gemini-3.1-flash-image-preview"))
    op.add_column("pipeline_settings", sa.Column("imagegen_prompt", sa.Text(), nullable=False, server_default=""))
    op.add_column("pipeline_settings", sa.Column("imagegen_size", sa.String(20), nullable=False, server_default="9:16"))
    op.add_column("pipeline_settings", sa.Column("imagegen_quality", sa.String(10), nullable=False, server_default="2K"))


def downgrade() -> None:
    op.drop_column("pipeline_settings", "imagegen_quality")
    op.drop_column("pipeline_settings", "imagegen_size")
    op.drop_column("pipeline_settings", "imagegen_prompt")
    op.drop_column("pipeline_settings", "imagegen_model")
