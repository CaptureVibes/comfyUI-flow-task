"""add_video_task_configs_table

Revision ID: dbaa90e756dc
Revises: 4a84e2de9864
Create Date: 2026-03-09 16:58:28.551549

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dbaa90e756dc'
down_revision = '0042'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "video_task_configs",
        sa.Column("owner_id", sa.UUID(), primary_key=True),
        sa.Column("round1_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("round1_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("round1_model", sa.String(200), nullable=False, server_default="gemini-2.0-flash"),
        sa.Column("round1_threshold", sa.Float(), nullable=False, server_default="60.0"),
        sa.Column("round1_weight", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("round2_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("round2_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("round2_model", sa.String(200), nullable=False, server_default="gemini-2.0-flash"),
        sa.Column("round2_threshold", sa.Float(), nullable=False, server_default="70.0"),
        sa.Column("round2_weight", sa.Float(), nullable=False, server_default="0.3"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("video_task_configs")
