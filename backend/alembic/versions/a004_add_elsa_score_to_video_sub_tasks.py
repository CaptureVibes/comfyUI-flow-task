"""add elsa_score to video_sub_tasks

Revision ID: a004
Revises: a003
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa

revision = "a004_elsa_score"
down_revision = "a003_multi_scoring"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("video_sub_tasks", sa.Column("elsa_score", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("video_sub_tasks", "elsa_score")
