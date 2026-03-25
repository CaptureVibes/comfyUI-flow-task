"""add import_attempts to candidate_videos

Revision ID: a014_import_attempts
Revises: a013_video_source_id
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = "a014_import_attempts"
down_revision = "a013_video_source_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    existing_cols = {c["name"] for c in sa.inspect(conn).get_columns("candidate_videos")}

    if "import_attempts" not in existing_cols:
        op.add_column(
            "candidate_videos",
            sa.Column("import_attempts", sa.Integer(), server_default="0", nullable=False),
        )


def downgrade() -> None:
    conn = op.get_bind()
    existing_cols = {c["name"] for c in sa.inspect(conn).get_columns("candidate_videos")}

    if "import_attempts" in existing_cols:
        op.drop_column("candidate_videos", "import_attempts")
